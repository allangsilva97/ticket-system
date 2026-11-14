from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from database import get_db, utcnow
from models import Ticket, Company, User, TicketStatus, UserRole
from schemas import DashboardStats
from auth import get_current_active_user
from routers.tickets import to_ticket_list

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

FINAL_STATUSES = [TicketStatus.CLOSED, TicketStatus.CANCELLED]


def _scoped_ticket_query(db: Session, current_user: User):
    query = db.query(Ticket)
    if current_user.role == UserRole.CLIENT:
        query = query.filter(Ticket.company_id == current_user.company_id)
    elif current_user.role == UserRole.AGENT:
        query = query.filter(
            (Ticket.company_id == current_user.company_id) | (Ticket.assignee_id == current_user.id)
        )
    return query


@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    ticket_query = _scoped_ticket_query(db, current_user)
    company_query = db.query(Company)
    user_query = db.query(User)

    if current_user.role != UserRole.ADMIN:
        company_query = company_query.filter(Company.id == current_user.company_id)
        user_query = user_query.filter(User.company_id == current_user.company_id)

    def grouped(column):
        return dict(ticket_query.with_entities(column, func.count(Ticket.id)).group_by(column).all())

    status_counts = grouped(Ticket.status)
    priority_counts = grouped(Ticket.priority)
    category_counts = grouped(Ticket.category)

    overdue_count = ticket_query.filter(
        Ticket.sla_due_at < utcnow(),
        Ticket.status.not_in(FINAL_STATUSES),
    ).count()

    loaders = (joinedload(Ticket.company), joinedload(Ticket.creator), joinedload(Ticket.assignee))

    recent = ticket_query.options(*loaders).order_by(Ticket.created_at.desc()).limit(5).all()

    my_tickets = []
    if current_user.role in [UserRole.ADMIN, UserRole.AGENT]:
        assigned = (ticket_query.options(*loaders)
                    .filter(Ticket.assignee_id == current_user.id)
                    .order_by(Ticket.created_at.desc()).limit(10).all())
        my_tickets = [to_ticket_list(t) for t in assigned]

    return DashboardStats(
        total_tickets=ticket_query.count(),
        open_tickets=status_counts.get(TicketStatus.OPEN, 0),
        in_progress_tickets=status_counts.get(TicketStatus.IN_PROGRESS, 0),
        waiting_tickets=status_counts.get(TicketStatus.WAITING_CUSTOMER, 0)
        + status_counts.get(TicketStatus.WAITING_THIRD_PARTY, 0),
        closed_tickets=status_counts.get(TicketStatus.CLOSED, 0),
        overdue_tickets=overdue_count,
        total_companies=company_query.count(),
        total_users=user_query.count(),
        tickets_by_status={k.value: v for k, v in status_counts.items()},
        tickets_by_priority={k.value: v for k, v in priority_counts.items()},
        tickets_by_category={k.value: v for k, v in category_counts.items()},
        recent_tickets=[to_ticket_list(t) for t in recent],
        my_assigned_tickets=my_tickets,
    )


@router.get("/charts/tickets-by-date")
def get_tickets_by_date(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Ticket creation trend for chart"""
    since = utcnow() - timedelta(days=days)

    results = _scoped_ticket_query(db, current_user).filter(Ticket.created_at >= since).with_entities(
        func.date(Ticket.created_at).label("date"),
        func.count(Ticket.id).label("count"),
    ).group_by(func.date(Ticket.created_at)).all()

    # func.date returns a string on SQLite and a date on MySQL/Postgres - normalize to ISO string
    results_dict = {str(r.date): r.count for r in results}

    data = []
    current = since.date()
    end = utcnow().date()
    while current <= end:
        data.append({"date": current.isoformat(), "count": results_dict.get(current.isoformat(), 0)})
        current += timedelta(days=1)

    return {"data": data}


@router.get("/charts/sla-compliance")
def get_sla_compliance(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """SLA compliance rate (closed tickets only - cancelled tickets have no resolution time)"""
    closed = _scoped_ticket_query(db, current_user).filter(
        Ticket.status == TicketStatus.CLOSED,
        Ticket.resolved_at.isnot(None),
        Ticket.sla_due_at.isnot(None),
    )

    total = closed.count()
    if total == 0:
        return {"compliance_rate": 100, "total_resolved": 0, "on_time": 0, "overdue": 0}

    on_time = closed.filter(Ticket.resolved_at <= Ticket.sla_due_at).count()

    return {
        "compliance_rate": round((on_time / total) * 100, 1),
        "total_resolved": total,
        "on_time": on_time,
        "overdue": total - on_time,
    }
