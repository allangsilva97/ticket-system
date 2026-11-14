import os
import uuid
from datetime import datetime
from math import ceil
from typing import Optional, List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, and_
from sqlalchemy.orm import Session, joinedload

from config import settings
from database import get_db, utcnow
from models import (
    Ticket, TicketComment, TicketAttachment, Company, User, UserRole, AuditLog,
    TicketStatus, TicketPriority, TicketCategory, AuditAction, AuditEntityType,
)
from schemas import (
    TicketCreate, TicketUpdate, Ticket as TicketSchema, TicketList, TicketStatusUpdate, TicketAssignment,
    CommentCreate, CommentUpdate, Comment, Attachment, PaginatedResponse,
)
from auth import (
    get_current_active_user, require_admin, require_agent_or_admin,
    can_view_ticket, can_edit_ticket, can_assign_ticket,
)
from services import audit_service as audit, email_service as mail
from services.sla_service import FINAL_STATUSES, calculate_sla_due, is_overdue, reset_notifications, sla_status

from routers.audit import audit_entry_to_dict  # noqa: E402

router = APIRouter(prefix="/api/tickets", tags=["Tickets"])

UPLOAD_DIR = settings.UPLOAD_DIR
MAX_FILE_SIZE = settings.max_file_size_bytes
ALLOWED_EXTENSIONS = settings.allowed_extensions_set

TICKET_LOADERS = (joinedload(Ticket.company), joinedload(Ticket.creator), joinedload(Ticket.assignee))


# ============ HELPERS ============

def ticket_is_overdue(ticket) -> bool:
    return is_overdue(ticket)


def to_ticket_list(t: Ticket) -> TicketList:
    return TicketList(
        id=t.id, tracking_code=t.tracking_code, title=t.title,
        status=t.status, priority=t.priority, category=t.category,
        company_name=t.company.name if t.company else "-", company_id=t.company_id,
        assignee_name=t.assignee.full_name if t.assignee else None,
        assignee_id=t.assignee_id,
        creator_name=t.creator.full_name if t.creator else "-",
        created_at=t.created_at, updated_at=t.updated_at,
        sla_due_at=t.sla_due_at, is_overdue=ticket_is_overdue(t),
    )


def build_ticket_response(db: Session, ticket_id: int) -> TicketSchema:
    ticket = db.query(Ticket).options(*TICKET_LOADERS).filter(Ticket.id == ticket_id).first()
    schema = TicketSchema.model_validate(ticket)
    schema.comment_count = db.query(func.count(TicketComment.id)).filter(
        TicketComment.ticket_id == ticket.id).scalar() or 0
    schema.attachment_count = db.query(func.count(TicketAttachment.id)).filter(
        TicketAttachment.ticket_id == ticket.id).scalar() or 0
    schema.is_overdue = ticket_is_overdue(ticket)
    return schema


def get_ticket_or_404(db: Session, ticket_id: int) -> Ticket:
    ticket = db.query(Ticket).options(*TICKET_LOADERS).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


def validate_assignee(db: Session, assignee_id: Optional[int], current_user: User):
    if not assignee_id:
        return
    assignee = db.query(User).filter(User.id == assignee_id).first()
    if not assignee:
        raise HTTPException(status_code=404, detail="Assignee not found")
    if not assignee.is_active:
        raise HTTPException(status_code=400, detail="Assignee is inactive")
    if assignee.role not in [UserRole.ADMIN, UserRole.AGENT]:
        raise HTTPException(status_code=400, detail="Can only assign to agents or admins")
    if current_user.role != UserRole.ADMIN and assignee.company_id != current_user.company_id:
        raise HTTPException(status_code=403, detail="Can only assign to users in your company")


def apply_status_change(ticket: Ticket, new_status: TicketStatus):
    old_status = ticket.status
    now = utcnow()
    if new_status == TicketStatus.CLOSED and old_status != TicketStatus.CLOSED:
        ticket.closed_at = now
        ticket.resolved_at = now
    elif old_status == TicketStatus.CLOSED and new_status != TicketStatus.CLOSED:
        ticket.closed_at = None
        ticket.resolved_at = None
    if old_status == TicketStatus.OPEN and new_status == TicketStatus.IN_PROGRESS and not ticket.first_response_at:
        ticket.first_response_at = now
    ticket.status = new_status


# ============ TICKETS ============

@router.post("", response_model=TicketSchema, status_code=201)
def create_ticket(
    ticket_data: TicketCreate,
    request: Request,
    background: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    company = db.query(Company).filter(Company.id == ticket_data.company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    if not company.is_active:
        raise HTTPException(status_code=400, detail="Company is inactive")

    if current_user.role == UserRole.CLIENT and current_user.company_id != ticket_data.company_id:
        raise HTTPException(status_code=403, detail="Cannot create tickets for other companies")

    data = ticket_data.model_dump()
    if current_user.role == UserRole.CLIENT:
        data["assignee_id"] = None  # clients can't assign
    validate_assignee(db, data.get("assignee_id"), current_user)

    ticket = Ticket(**data, creator_id=current_user.id)
    ticket.sla_due_at = calculate_sla_due(company, ticket.priority)

    db.add(ticket)
    db.flush()  # assigns ticket.id for the audit entry
    audit.log(db, AuditEntityType.TICKET, ticket.id, AuditAction.CREATE, current_user,
              changes=audit.snapshot(ticket, audit.TICKET_FIELDS), request=request)
    db.commit()

    ticket = get_ticket_or_404(db, ticket.id)
    background.add_task(mail.send, mail.ticket_created(ticket, current_user))
    return build_ticket_response(db, ticket.id)


@router.get("", response_model=PaginatedResponse)
def list_tickets(
    status: Optional[TicketStatus] = None,
    priority: Optional[TicketPriority] = None,
    category: Optional[TicketCategory] = None,
    company_id: Optional[int] = None,
    assignee_id: Optional[int] = None,
    creator_id: Optional[int] = None,
    search: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    overdue_only: bool = False,
    unassigned: bool = False,
    open_only: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    query = db.query(Ticket).options(*TICKET_LOADERS)

    # Role-based visibility
    if current_user.role == UserRole.CLIENT:
        query = query.filter(Ticket.company_id == current_user.company_id)
    elif current_user.role == UserRole.AGENT:
        query = query.filter(or_(Ticket.company_id == current_user.company_id,
                                 Ticket.assignee_id == current_user.id))

    if status:
        query = query.filter(Ticket.status == status)
    if priority:
        query = query.filter(Ticket.priority == priority)
    if category:
        query = query.filter(Ticket.category == category)
    if company_id:
        if current_user.role == UserRole.CLIENT and current_user.company_id != company_id:
            raise HTTPException(status_code=403, detail="Access denied")
        query = query.filter(Ticket.company_id == company_id)
    if assignee_id:
        query = query.filter(Ticket.assignee_id == assignee_id)
    if creator_id:
        query = query.filter(Ticket.creator_id == creator_id)
    if search:
        query = query.filter(or_(Ticket.title.ilike(f"%{search}%"), Ticket.description.ilike(f"%{search}%")))
    if date_from:
        query = query.filter(Ticket.created_at >= date_from)
    if date_to:
        query = query.filter(Ticket.created_at <= date_to)
    if unassigned:
        query = query.filter(Ticket.assignee_id.is_(None))
    if open_only:
        query = query.filter(Ticket.status.not_in(FINAL_STATUSES))
    if overdue_only:
        query = query.filter(and_(Ticket.sla_due_at < utcnow(), Ticket.status.not_in(FINAL_STATUSES)))

    total = query.count()
    tickets = query.order_by(Ticket.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return PaginatedResponse(
        items=[to_ticket_list(t) for t in tickets],
        total=total, page=page, page_size=page_size,
        total_pages=ceil(total / page_size) if total else 0,
    )


@router.get("/my-assigned", response_model=List[TicketList])
def get_my_assigned_tickets(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in [UserRole.ADMIN, UserRole.AGENT]:
        raise HTTPException(status_code=403, detail="Agent or Admin access required")

    tickets = db.query(Ticket).options(*TICKET_LOADERS).filter(
        Ticket.assignee_id == current_user.id
    ).order_by(Ticket.created_at.desc()).limit(10).all()
    return [to_ticket_list(t) for t in tickets]


@router.get("/{ticket_id}", response_model=TicketSchema)
def get_ticket(
    ticket_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    ticket = get_ticket_or_404(db, ticket_id)
    if not can_view_ticket(ticket, current_user):
        raise HTTPException(status_code=403, detail="Access denied")
    return build_ticket_response(db, ticket.id)


@router.put("/{ticket_id}", response_model=TicketSchema)
def update_ticket(
    ticket_id: int,
    ticket_data: TicketUpdate,
    request: Request,
    background: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    ticket = get_ticket_or_404(db, ticket_id)
    if not can_edit_ticket(ticket, current_user):
        raise HTTPException(status_code=403, detail="Cannot edit this ticket")

    update_data = ticket_data.model_dump(exclude_unset=True)
    before = audit.snapshot(ticket, audit.TICKET_FIELDS)
    old_status, old_assignee = ticket.status, ticket.assignee_id

    # Clients can't change assignee, status or priority through this endpoint
    # (priority drives the SLA deadline, so clients could otherwise reset/escalate it)
    if current_user.role == UserRole.CLIENT:
        update_data.pop("assignee_id", None)
        update_data.pop("status", None)
        update_data.pop("priority", None)

    if "assignee_id" in update_data:
        validate_assignee(db, update_data["assignee_id"], current_user)

    new_status = update_data.pop("status", None)
    if new_status is not None and new_status != ticket.status:
        apply_status_change(ticket, new_status)

    if "priority" in update_data and update_data["priority"] != ticket.priority:
        ticket.sla_due_at = calculate_sla_due(ticket.company, update_data["priority"])
        reset_notifications(ticket)

    for field, value in update_data.items():
        setattr(ticket, field, value)

    changes = audit.diff(before, audit.snapshot(ticket, audit.TICKET_FIELDS))
    if changes:
        ticket.updated_at = utcnow()
        audit.log(db, AuditEntityType.TICKET, ticket.id, audit.ticket_update_action(changes),
                  current_user, changes=changes, request=request)
    db.commit()

    ticket = get_ticket_or_404(db, ticket.id)
    if ticket.status != old_status:
        background.add_task(mail.send, mail.status_changed(ticket, old_status.value, current_user))
    if ticket.assignee_id and ticket.assignee_id != old_assignee:
        background.add_task(mail.send, mail.ticket_assigned(ticket, current_user))
    return build_ticket_response(db, ticket.id)


@router.put("/{ticket_id}/status", response_model=TicketSchema)
def update_ticket_status(
    ticket_id: int,
    status_data: TicketStatusUpdate,
    request: Request,
    background: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    ticket = get_ticket_or_404(db, ticket_id)

    if current_user.role == UserRole.CLIENT:
        # Clients can only reopen or cancel their own tickets
        if ticket.creator_id != current_user.id:
            raise HTTPException(status_code=403, detail="Can only update your own tickets")
        if status_data.status not in [TicketStatus.OPEN, TicketStatus.CANCELLED]:
            raise HTTPException(status_code=403, detail="Clients can only reopen or cancel tickets")
    elif not can_edit_ticket(ticket, current_user):
        raise HTTPException(status_code=403, detail="Cannot update this ticket")

    if status_data.status != ticket.status:
        old_status = ticket.status
        apply_status_change(ticket, status_data.status)
        ticket.updated_at = utcnow()
        audit.log(db, AuditEntityType.TICKET, ticket.id, AuditAction.STATUS_CHANGE, current_user,
                  changes={"status": {"old": old_status.value, "new": ticket.status.value}}, request=request)
        db.commit()
        ticket = get_ticket_or_404(db, ticket.id)
        background.add_task(mail.send, mail.status_changed(ticket, old_status.value, current_user))
    return build_ticket_response(db, ticket.id)


@router.put("/{ticket_id}/assign", response_model=TicketSchema)
def assign_ticket(
    ticket_id: int,
    assignment: TicketAssignment,
    request: Request,
    background: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if not can_assign_ticket(current_user):
        raise HTTPException(status_code=403, detail="Cannot assign tickets")

    ticket = get_ticket_or_404(db, ticket_id)
    if not can_view_ticket(ticket, current_user):
        raise HTTPException(status_code=403, detail="Access denied")

    validate_assignee(db, assignment.assignee_id, current_user)

    before = audit.snapshot(ticket, audit.TICKET_FIELDS)
    old_assignee = ticket.assignee_id
    ticket.assignee_id = assignment.assignee_id
    ticket.updated_at = utcnow()

    # Auto-transition to in_progress if assigned while open
    if assignment.assignee_id and ticket.status == TicketStatus.OPEN:
        apply_status_change(ticket, TicketStatus.IN_PROGRESS)

    changes = audit.diff(before, audit.snapshot(ticket, audit.TICKET_FIELDS))
    if changes:
        audit.log(db, AuditEntityType.TICKET, ticket.id, AuditAction.ASSIGNMENT, current_user,
                  changes=changes, request=request)
    db.commit()

    ticket = get_ticket_or_404(db, ticket.id)
    if ticket.assignee_id and ticket.assignee_id != old_assignee:
        background.add_task(mail.send, mail.ticket_assigned(ticket, current_user))
    return build_ticket_response(db, ticket.id)


@router.delete("/{ticket_id}", status_code=204)
def delete_ticket(
    ticket_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    file_paths = [a.file_path for a in ticket.attachments]
    audit.log(db, AuditEntityType.TICKET, ticket.id, AuditAction.DELETE, current_user,
              changes=audit.snapshot(ticket, audit.TICKET_FIELDS), request=request)
    db.delete(ticket)
    db.commit()

    for path in file_paths:
        if os.path.exists(path):
            os.remove(path)


# ============ SLA & HISTORY ============

@router.get("/{ticket_id}/sla")
def get_ticket_sla(
    ticket_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Current SLA state: ok / warning / breached / closed / no_sla."""
    ticket = get_ticket_or_404(db, ticket_id)
    if not can_view_ticket(ticket, current_user):
        raise HTTPException(status_code=403, detail="Access denied")
    return {"ticket_id": ticket.id, **sla_status(ticket)}


@router.get("/{ticket_id}/history")
def get_ticket_history(
    ticket_id: int,
    current_user: User = Depends(require_agent_or_admin),
    db: Session = Depends(get_db),
):
    """Audit trail of one ticket (staff only)."""
    ticket = get_ticket_or_404(db, ticket_id)
    if not can_view_ticket(ticket, current_user):
        raise HTTPException(status_code=403, detail="Access denied")
    entries = db.query(AuditLog).filter(
        AuditLog.entity_type == AuditEntityType.TICKET, AuditLog.entity_id == ticket_id
    ).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(200).all()
    return [audit_entry_to_dict(e) for e in entries]


# ============ COMMENTS ============

def _comment_to_schema(c: TicketComment) -> Comment:
    return Comment(
        id=c.id, ticket_id=c.ticket_id, author_id=c.author_id,
        author_name=c.author.full_name, author_role=c.author.role,
        content=c.content, is_internal=c.is_internal,
        created_at=c.created_at, updated_at=c.updated_at,
    )


@router.post("/{ticket_id}/comments", response_model=Comment, status_code=201)
def add_comment(
    ticket_id: int,
    comment_data: CommentCreate,
    request: Request,
    background: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    ticket = get_ticket_or_404(db, ticket_id)
    if not can_view_ticket(ticket, current_user):
        raise HTTPException(status_code=403, detail="Access denied")

    is_internal = comment_data.is_internal and current_user.role != UserRole.CLIENT

    comment = TicketComment(
        ticket_id=ticket_id, author_id=current_user.id,
        content=comment_data.content, is_internal=is_internal,
    )
    db.add(comment)
    db.flush()
    audit.log(db, AuditEntityType.TICKET, ticket.id, AuditAction.COMMENT_ADD, current_user,
              changes={"comment_id": comment.id, "is_internal": is_internal}, request=request)
    ticket.updated_at = utcnow()

    # Client reply on a ticket waiting for them -> back to open
    if current_user.role == UserRole.CLIENT and ticket.status == TicketStatus.WAITING_CUSTOMER:
        ticket.status = TicketStatus.OPEN

    # First public response by staff counts as first response
    if current_user.role != UserRole.CLIENT and not is_internal and not ticket.first_response_at:
        ticket.first_response_at = utcnow()

    db.commit()
    db.refresh(comment)
    background.add_task(mail.send, mail.comment_added(ticket, comment.content, is_internal, current_user))
    return _comment_to_schema(comment)


@router.get("/{ticket_id}/comments", response_model=List[Comment])
def get_comments(
    ticket_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    ticket = get_ticket_or_404(db, ticket_id)
    if not can_view_ticket(ticket, current_user):
        raise HTTPException(status_code=403, detail="Access denied")

    query = db.query(TicketComment).options(joinedload(TicketComment.author)).filter(
        TicketComment.ticket_id == ticket_id)

    if current_user.role == UserRole.CLIENT:
        query = query.filter(TicketComment.is_internal == False)  # noqa: E712

    return [_comment_to_schema(c) for c in query.order_by(TicketComment.created_at).all()]


@router.put("/comments/{comment_id}", response_model=Comment)
def update_comment(
    comment_id: int,
    comment_data: CommentUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    comment = db.query(TicketComment).filter(TicketComment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    if comment.author_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Cannot edit this comment")

    update_data = comment_data.model_dump(exclude_unset=True)
    if current_user.role == UserRole.CLIENT:
        update_data.pop("is_internal", None)

    for field, value in update_data.items():
        setattr(comment, field, value)

    comment.updated_at = utcnow()
    db.commit()
    db.refresh(comment)
    return _comment_to_schema(comment)


@router.delete("/comments/{comment_id}", status_code=204)
def delete_comment(
    comment_id: int,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    comment = db.query(TicketComment).filter(TicketComment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    if comment.author_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Cannot delete this comment")

    audit.log(db, AuditEntityType.TICKET, comment.ticket_id, AuditAction.COMMENT_DELETE, current_user,
              changes={"comment_id": comment.id, "content": comment.content[:500]}, request=request)
    db.delete(comment)
    db.commit()


# ============ ATTACHMENTS ============

def _attachment_to_schema(a: TicketAttachment) -> Attachment:
    return Attachment(
        id=a.id, ticket_id=a.ticket_id, filename=a.filename,
        original_filename=a.original_filename, content_type=a.content_type,
        file_size=a.file_size, file_path=a.filename,  # don't leak server paths
        uploaded_by_id=a.uploaded_by_id,
        uploaded_by_name=a.uploaded_by.full_name if a.uploaded_by else "-",
        created_at=a.created_at,
    )


@router.post("/{ticket_id}/attachments", response_model=Attachment, status_code=201)
def upload_attachment(
    ticket_id: int,
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    ticket = get_ticket_or_404(db, ticket_id)
    if not can_view_ticket(ticket, current_user):
        raise HTTPException(status_code=403, detail="Access denied")

    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400,
                            detail=f"File type not allowed. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}")

    # Read at most MAX+1 bytes so huge uploads are not loaded entirely in memory
    content = file.file.read(MAX_FILE_SIZE + 1)
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"File too large. Max size: {MAX_FILE_SIZE // (1024 * 1024)}MB")

    unique_filename = f"{uuid.uuid4()}{ext}"
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    with open(file_path, "wb") as f:
        f.write(content)

    attachment = TicketAttachment(
        ticket_id=ticket_id,
        filename=unique_filename,
        original_filename=os.path.basename(file.filename),
        content_type=file.content_type,
        file_size=len(content),
        file_path=file_path,
        uploaded_by_id=current_user.id,
    )
    db.add(attachment)
    ticket.updated_at = utcnow()
    try:
        db.flush()
        audit.log(db, AuditEntityType.TICKET, ticket.id, AuditAction.ATTACHMENT_UPLOAD, current_user,
                  changes={"attachment_id": attachment.id, "filename": attachment.original_filename,
                           "size": attachment.file_size}, request=request)
        db.commit()
    except Exception:
        # Don't leave an orphan file on disk when the DB write fails
        db.rollback()
        if os.path.exists(file_path):
            os.remove(file_path)
        raise
    db.refresh(attachment)
    return _attachment_to_schema(attachment)


@router.get("/{ticket_id}/attachments", response_model=List[Attachment])
def list_attachments(
    ticket_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    ticket = get_ticket_or_404(db, ticket_id)
    if not can_view_ticket(ticket, current_user):
        raise HTTPException(status_code=403, detail="Access denied")

    attachments = db.query(TicketAttachment).options(joinedload(TicketAttachment.uploaded_by)).filter(
        TicketAttachment.ticket_id == ticket_id).order_by(TicketAttachment.created_at.desc()).all()
    return [_attachment_to_schema(a) for a in attachments]


def _get_attachment_checked(db: Session, attachment_id: int, current_user: User) -> TicketAttachment:
    attachment = db.query(TicketAttachment).filter(TicketAttachment.id == attachment_id).first()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    ticket = db.query(Ticket).filter(Ticket.id == attachment.ticket_id).first()
    if not ticket or not can_view_ticket(ticket, current_user):
        raise HTTPException(status_code=403, detail="Access denied")
    return attachment


@router.get("/attachments/{attachment_id}/download")
def download_attachment(
    attachment_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Authenticated download (files are no longer served publicly from /uploads)."""
    attachment = _get_attachment_checked(db, attachment_id, current_user)
    if not os.path.exists(attachment.file_path):
        raise HTTPException(status_code=404, detail="File missing on server")
    return FileResponse(
        attachment.file_path,
        media_type=attachment.content_type or "application/octet-stream",
        filename=attachment.original_filename,
    )


@router.delete("/attachments/{attachment_id}", status_code=204)
def delete_attachment(
    attachment_id: int,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    attachment = _get_attachment_checked(db, attachment_id, current_user)

    # Clients may only delete their own uploads
    if current_user.role == UserRole.CLIENT and attachment.uploaded_by_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot delete this attachment")

    path = attachment.file_path
    audit.log(db, AuditEntityType.TICKET, attachment.ticket_id, AuditAction.ATTACHMENT_DELETE, current_user,
              changes={"attachment_id": attachment.id, "filename": attachment.original_filename}, request=request)
    db.delete(attachment)
    db.commit()
    if os.path.exists(path):
        os.remove(path)
