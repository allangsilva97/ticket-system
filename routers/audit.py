from datetime import datetime
from math import ceil
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from auth import require_admin
from database import get_db
from models import AuditAction, AuditEntityType, AuditLog, User
from schemas import PaginatedResponse

router = APIRouter(prefix="/api/audit", tags=["Audit"])


def audit_entry_to_dict(e: AuditLog) -> dict:
    return {
        "id": e.id,
        "entity_type": e.entity_type.value,
        "entity_id": e.entity_id,
        "action": e.action.value,
        "changes": e.changes,
        "description": e.description,
        "user_id": e.user_id,
        "user_name": e.user_name,
        "user_role": e.user_role,
        "ip_address": e.ip_address,
        "created_at": e.created_at,
    }


@router.get("", response_model=PaginatedResponse)
def list_audit_logs(
    entity_type: Optional[AuditEntityType] = None,
    entity_id: Optional[int] = None,
    action: Optional[AuditAction] = None,
    user_id: Optional[int] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Full audit trail (admins only), newest first."""
    query = db.query(AuditLog)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        query = query.filter(AuditLog.entity_id == entity_id)
    if action:
        query = query.filter(AuditLog.action == action)
    if user_id is not None:
        query = query.filter(AuditLog.user_id == user_id)
    if date_from:
        query = query.filter(AuditLog.created_at >= date_from)
    if date_to:
        query = query.filter(AuditLog.created_at <= date_to)

    total = query.count()
    rows = (query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .offset((page - 1) * page_size).limit(page_size).all())
    return PaginatedResponse(
        items=[audit_entry_to_dict(e) for e in rows],
        total=total, page=page, page_size=page_size,
        total_pages=ceil(total / page_size) if total else 0,
    )
