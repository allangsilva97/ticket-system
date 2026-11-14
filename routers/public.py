"""Public (no login) endpoints.

Anyone holding a ticket's tracking code can follow it. Only customer-facing data
is exposed: no internal notes, no e-mails, no attachments, no audit trail.
"""
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import Ticket, TicketComment, UserRole, TRACKING_CODE_LENGTH
from services.sla_service import is_overdue

router = APIRouter(prefix="/api/public", tags=["Public"])


def normalize_code(code: str) -> str:
    """Accept what people actually type: lowercase, spaces, dashes."""
    return re.sub(r"[^A-Za-z0-9]", "", code).upper()


def _first_name(user) -> str:
    return user.full_name.split()[0] if user and user.full_name else "-"


@router.get("/tickets/{code}")
def track_ticket(code: str, db: Session = Depends(get_db)):
    code = normalize_code(code)
    # Same message for malformed and unknown codes: don't help anyone probe
    not_found = HTTPException(status_code=404, detail="Chamado não encontrado. Confira o código.")
    if len(code) != TRACKING_CODE_LENGTH:
        raise not_found

    ticket = db.query(Ticket).options(
        joinedload(Ticket.company), joinedload(Ticket.assignee)
    ).filter(Ticket.tracking_code == code).first()
    if not ticket:
        raise not_found

    comments = db.query(TicketComment).options(joinedload(TicketComment.author)).filter(
        TicketComment.ticket_id == ticket.id,
        TicketComment.is_internal == False,  # noqa: E712
    ).order_by(TicketComment.created_at).all()

    return {
        "tracking_code": ticket.tracking_code,
        "id": ticket.id,
        "title": ticket.title,
        "description": ticket.description,
        "status": ticket.status.value,
        "priority": ticket.priority.value,
        "category": ticket.category.value,
        "company_name": ticket.company.name if ticket.company else None,
        "assignee_name": _first_name(ticket.assignee) if ticket.assignee else None,
        "created_at": ticket.created_at,
        "updated_at": ticket.updated_at,
        "first_response_at": ticket.first_response_at,
        "closed_at": ticket.closed_at,
        "sla_due_at": ticket.sla_due_at,
        "is_overdue": is_overdue(ticket),
        "comments": [
            {
                "author_name": _first_name(c.author),
                "is_staff": c.author.role != UserRole.CLIENT if c.author else False,
                "content": c.content,
                "created_at": c.created_at,
            }
            for c in comments
        ],
    }
