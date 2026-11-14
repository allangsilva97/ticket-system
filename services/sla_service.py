"""SLA calculation and the background monitor that sends warning/breach alerts."""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from config import settings
from database import SessionLocal, utcnow
from models import Ticket, TicketPriority, TicketStatus, User, UserRole
from services import email_service

logger = logging.getLogger("ticket_system.sla")

FINAL_STATUSES = (TicketStatus.CLOSED, TicketStatus.CANCELLED)

# SLA time = company SLA hours x multiplier
PRIORITY_MULTIPLIERS = {
    TicketPriority.CRITICAL: 0.25,
    TicketPriority.URGENT: 0.5,
    TicketPriority.HIGH: 0.75,
    TicketPriority.MEDIUM: 1.0,
    TicketPriority.LOW: 2.0,
}


def calculate_sla_due(company, priority: TicketPriority, start: Optional[datetime] = None) -> datetime:
    base_hours = company.sla_hours if company and company.sla_hours else 24
    return (start or utcnow()) + timedelta(hours=base_hours * PRIORITY_MULTIPLIERS.get(priority, 1.0))


def is_overdue(ticket: Ticket, now: Optional[datetime] = None) -> bool:
    return bool(ticket.sla_due_at and ticket.sla_due_at < (now or utcnow())
                and ticket.status not in FINAL_STATUSES)


def elapsed_fraction(ticket: Ticket, now: Optional[datetime] = None) -> float:
    if not ticket.sla_due_at or not ticket.created_at:
        return 0.0
    total = (ticket.sla_due_at - ticket.created_at).total_seconds()
    if total <= 0:
        return 1.0
    return ((now or utcnow()) - ticket.created_at).total_seconds() / total


def format_delta(delta: timedelta) -> str:
    seconds = max(int(delta.total_seconds()), 0)
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    parts = [f"{days}d"] if days else []
    if hours:
        parts.append(f"{hours}h")
    if minutes or not parts:
        parts.append(f"{minutes}m")
    return " ".join(parts)


def sla_status(ticket: Ticket, now: Optional[datetime] = None) -> Dict:
    """Snapshot of the SLA state of one ticket (used by GET /api/tickets/{id}/sla)."""
    now = now or utcnow()
    if ticket.status in FINAL_STATUSES:
        met = None
        if ticket.sla_due_at and ticket.resolved_at:
            met = ticket.resolved_at <= ticket.sla_due_at
        return {"status": "closed", "sla_met": met, "due_at": ticket.sla_due_at}
    if not ticket.sla_due_at:
        return {"status": "no_sla", "due_at": None}

    fraction = round(elapsed_fraction(ticket, now), 4)
    if now > ticket.sla_due_at:
        return {"status": "breached", "elapsed": fraction, "due_at": ticket.sla_due_at,
                "overdue_by": format_delta(now - ticket.sla_due_at)}
    state = "warning" if fraction >= settings.SLA_WARNING_THRESHOLD else "ok"
    return {"status": state, "elapsed": fraction, "due_at": ticket.sla_due_at,
            "time_left": format_delta(ticket.sla_due_at - now)}


# ============ Monitor ============

def run_sla_check(db: Session, now: Optional[datetime] = None) -> Dict[str, int]:
    """Send each SLA warning/breach alert once per ticket. Returns how many were sent."""
    now = now or utcnow()
    open_tickets = (
        db.query(Ticket)
        .options(joinedload(Ticket.assignee), joinedload(Ticket.company))
        .filter(
            Ticket.status.not_in(FINAL_STATUSES),
            Ticket.sla_due_at.isnot(None),
            or_(Ticket.sla_breach_notified_at.is_(None), Ticket.sla_warning_notified_at.is_(None)),
        )
        .all()
    )

    admins = None
    sent = {"warnings": 0, "breaches": 0}
    for ticket in open_tickets:
        if ticket.sla_due_at < now:
            if ticket.sla_breach_notified_at is None:
                if admins is None:
                    admins = db.query(User).filter(User.role == UserRole.ADMIN, User.is_active.is_(True)).all()
                email_service.send(email_service.sla_breach(ticket, admins))
                ticket.sla_breach_notified_at = now
                ticket.sla_warning_notified_at = ticket.sla_warning_notified_at or now
                sent["breaches"] += 1
        elif ticket.sla_warning_notified_at is None and elapsed_fraction(ticket, now) >= settings.SLA_WARNING_THRESHOLD:
            email_service.send(email_service.sla_warning(ticket, format_delta(ticket.sla_due_at - now)))
            ticket.sla_warning_notified_at = now
            sent["warnings"] += 1
    db.commit()
    return sent


def reset_notifications(ticket: Ticket) -> None:
    """Call when the SLA deadline moves (priority change, reopen) so alerts fire again."""
    ticket.sla_warning_notified_at = None
    ticket.sla_breach_notified_at = None


def _check_once() -> None:
    db = SessionLocal()
    try:
        result = run_sla_check(db)
        if result["warnings"] or result["breaches"]:
            logger.info("SLA check: %s", result)
    except Exception:  # keep the monitor alive whatever happens
        db.rollback()
        logger.exception("SLA check failed")
    finally:
        db.close()


async def sla_monitor_loop() -> None:
    interval = max(settings.SLA_CHECK_INTERVAL_MINUTES, 1) * 60
    while True:
        # Blocking DB/SMTP work runs in a thread so the event loop stays free
        await asyncio.to_thread(_check_once)
        await asyncio.sleep(interval)
