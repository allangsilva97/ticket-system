"""Audit trail: records who changed what, and when.

Entries are added to the caller's session and committed together with the
change itself, so a rolled-back change never leaves a stray audit row.
"""
import enum
from datetime import datetime
from typing import Any, Dict, Iterable, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from models import AuditAction, AuditEntityType, AuditLog, User

TICKET_FIELDS = ("title", "description", "status", "priority", "category",
                 "company_id", "assignee_id", "sla_due_at")
COMPANY_FIELDS = ("name", "email", "phone", "address", "city", "country",
                  "timezone", "sla_hours", "is_active")
USER_FIELDS = ("email", "full_name", "role", "language", "company_id", "is_active")


def _plain(value: Any) -> Any:
    """Make a value JSON-serialisable (enums, datetimes)."""
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def snapshot(obj: Any, fields: Iterable[str]) -> Dict[str, Any]:
    return {f: _plain(getattr(obj, f, None)) for f in fields}


def diff(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {k: {"old": before.get(k), "new": v} for k, v in after.items() if before.get(k) != v}


def client_ip(request: Optional[Request]) -> Optional[str]:
    if request is None or request.client is None:
        return None
    return request.client.host


def log(
    db: Session,
    entity_type: AuditEntityType,
    entity_id: int,
    action: AuditAction,
    user: Optional[User] = None,
    changes: Optional[Dict[str, Any]] = None,
    description: Optional[str] = None,
    request: Optional[Request] = None,
) -> AuditLog:
    entry = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        changes=changes or None,
        description=description or _describe(entity_type, action, changes),
        user_id=user.id if user else None,
        user_name=user.full_name if user else "System",
        user_role=user.role.value if user else None,
        ip_address=client_ip(request),
    )
    db.add(entry)
    return entry


_ACTION_TEXT = {
    AuditAction.CREATE: "created",
    AuditAction.UPDATE: "updated",
    AuditAction.DELETE: "deleted",
    AuditAction.STATUS_CHANGE: "status changed",
    AuditAction.ASSIGNMENT: "assignee changed",
    AuditAction.COMMENT_ADD: "comment added",
    AuditAction.COMMENT_DELETE: "comment deleted",
    AuditAction.ATTACHMENT_UPLOAD: "attachment uploaded",
    AuditAction.ATTACHMENT_DELETE: "attachment deleted",
    AuditAction.LOGIN: "logged in",
    AuditAction.PASSWORD_CHANGE: "password changed",
}


def _describe(entity_type: AuditEntityType, action: AuditAction, changes: Optional[Dict[str, Any]]) -> str:
    text = f"{entity_type.value.capitalize()} {_ACTION_TEXT.get(action, action.value)}"
    if action in (AuditAction.UPDATE, AuditAction.STATUS_CHANGE, AuditAction.ASSIGNMENT) and changes:
        text += f" (fields: {', '.join(sorted(changes))})"
    return text


def ticket_update_action(changes: Dict[str, Any]) -> AuditAction:
    if "status" in changes:
        return AuditAction.STATUS_CHANGE
    if "assignee_id" in changes:
        return AuditAction.ASSIGNMENT
    return AuditAction.UPDATE
