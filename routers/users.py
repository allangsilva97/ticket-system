from math import ceil
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import User, UserRole, Ticket
from schemas import User as UserSchema, PaginatedResponse, TicketList
from auth import get_current_active_user, require_agent_or_admin
from routers.tickets import to_ticket_list

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.get("", response_model=PaginatedResponse)
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    role: Optional[UserRole] = None,
    company_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    current_user: User = Depends(require_agent_or_admin),
    db: Session = Depends(get_db),
):
    query = db.query(User).options(joinedload(User.company))

    # Agents only see users of their own company
    if current_user.role != UserRole.ADMIN:
        query = query.filter(User.company_id == current_user.company_id)

    if role:
        query = query.filter(User.role == role)
    if company_id:
        if current_user.role != UserRole.ADMIN and current_user.company_id != company_id:
            raise HTTPException(status_code=403, detail="Access denied")
        query = query.filter(User.company_id == company_id)
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    if search:
        query = query.filter(or_(User.full_name.ilike(f"%{search}%"), User.email.ilike(f"%{search}%")))

    total = query.count()
    users = query.order_by(User.full_name).offset((page - 1) * page_size).limit(page_size).all()

    return PaginatedResponse(
        items=[UserSchema.model_validate(u) for u in users],
        total=total, page=page, page_size=page_size,
        total_pages=ceil(total / page_size) if total else 0,
    )


@router.get("/agents", response_model=List[UserSchema])
def list_agents(
    company_id: Optional[int] = None,
    current_user: User = Depends(require_agent_or_admin),
    db: Session = Depends(get_db),
):
    """List of agents/admins for the assignment dropdown"""
    query = db.query(User).filter(
        User.role.in_([UserRole.ADMIN, UserRole.AGENT]),
        User.is_active == True,  # noqa: E712
    )

    if current_user.role != UserRole.ADMIN:
        query = query.filter(User.company_id == current_user.company_id)
    elif company_id:
        query = query.filter(User.company_id == company_id)

    return query.order_by(User.full_name).all()


@router.get("/{user_id}/tickets", response_model=List[TicketList])
def get_user_tickets(
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    if current_user.role != UserRole.ADMIN:
        if current_user.id != user_id and current_user.company_id != target_user.company_id:
            raise HTTPException(status_code=403, detail="Access denied")

    query = db.query(Ticket).options(
        joinedload(Ticket.company), joinedload(Ticket.creator), joinedload(Ticket.assignee)
    ).filter(or_(Ticket.creator_id == user_id, Ticket.assignee_id == user_id))

    # Clients must not see tickets of other companies through this endpoint
    if current_user.role == UserRole.CLIENT:
        query = query.filter(Ticket.company_id == current_user.company_id)

    tickets = query.order_by(Ticket.created_at.desc()).limit(50).all()
    return [to_ticket_list(t) for t in tickets]
