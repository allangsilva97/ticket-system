"""E-mail notifications.

Without SMTP_HOST configured, e-mails are only written to the log, so the
system works out of the box in development. Messages are rendered while the
request's DB session is still open and sent afterwards in a FastAPI
background task (or in the SLA monitor), never blocking the request.
"""
import html
import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr
from typing import Iterable, List, NamedTuple, Optional

from config import settings
from models import Ticket, User

logger = logging.getLogger("ticket_system.email")


class Email(NamedTuple):
    to: List[str]
    subject: str
    html: str


def _recipients(users: Iterable[Optional[User]], exclude: Optional[User] = None) -> List[str]:
    seen, result = set(), []
    for u in users:
        if u is None or not u.email or not u.is_active:
            continue
        if exclude is not None and u.id == exclude.id:
            continue
        if u.email not in seen:
            seen.add(u.email)
            result.append(u.email)
    return result


def _layout(title: str, body_html: str, ticket_id: Optional[int] = None) -> str:
    button = ""
    if ticket_id is not None:
        link = html.escape(f"{settings.APP_URL.rstrip('/')}/#ticket-{ticket_id}")
        button = (f'<p style="text-align:center"><a href="{link}" style="display:inline-block;'
                  'padding:10px 20px;background:#6c5ce7;color:#fff;text-decoration:none;'
                  'border-radius:6px">Ver ticket</a></p>')
    return f"""<!DOCTYPE html><html><body style="font-family:Segoe UI,Arial,sans-serif;background:#f5f6fa;padding:24px">
<div style="max-width:600px;margin:auto;background:#fff;border-radius:10px;overflow:hidden">
<div style="background:#6c5ce7;color:#fff;padding:18px 24px"><h2 style="margin:0">{html.escape(title)}</h2></div>
<div style="padding:24px;color:#2d3436;line-height:1.5">{body_html}{button}</div>
<div style="padding:12px 24px;color:#636e72;font-size:12px;border-top:1px solid #eee">
{html.escape(settings.APP_NAME)}</div>
</div></body></html>"""


def _ticket_block(t: Ticket) -> str:
    e = html.escape
    company = t.company.name if t.company else "-"
    return (f"<p><strong>#{t.id}</strong> {e(t.title)}<br>"
            f"Empresa: {e(company)}<br>Prioridade: {e(t.priority.value)}<br>"
            f"Status: {e(t.status.value)}</p>")


def send(email: Optional[Email]) -> bool:
    """Send one e-mail. Returns True when sent (or logged in dev mode)."""
    if email is None or not email.to or not settings.ENABLE_EMAIL_NOTIFICATIONS:
        return False
    if not settings.SMTP_HOST:
        logger.info("[email:dev] to=%s subject=%s", ", ".join(email.to), email.subject)
        return True

    msg = EmailMessage()
    msg["Subject"] = email.subject
    msg["From"] = formataddr((settings.EMAIL_FROM_NAME, settings.EMAIL_FROM))
    msg["To"] = ", ".join(email.to)
    msg.set_content("Este e-mail requer um cliente com suporte a HTML.")
    msg.add_alternative(email.html, subtype="html")
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=settings.SMTP_TIMEOUT) as smtp:
            if settings.SMTP_USE_TLS:
                smtp.starttls(context=ssl.create_default_context())
            if settings.SMTP_USER:
                smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            smtp.send_message(msg)
        return True
    except (OSError, smtplib.SMTPException) as exc:
        # A notification failure must never break the action that triggered it
        logger.error("Failed to send e-mail '%s': %s", email.subject, exc)
        return False


# ============ Message builders ============

def ticket_created(ticket: Ticket, by: User) -> Email:
    to = _recipients([ticket.assignee], exclude=by)
    body = _layout("Novo ticket", f"<p>Um novo ticket foi aberto por {html.escape(by.full_name)}.</p>"
                   f"{_ticket_block(ticket)}", ticket.id)
    return Email(to, f"[Ticket #{ticket.id}] Novo ticket: {ticket.title}", body)


def ticket_assigned(ticket: Ticket, by: User) -> Email:
    to = _recipients([ticket.assignee], exclude=by)
    name = ticket.assignee.full_name if ticket.assignee else ""
    body = _layout("Ticket atribuído a você",
                   f"<p>Olá {html.escape(name)},</p>"
                   f"<p>{html.escape(by.full_name)} atribuiu este ticket a você.</p>{_ticket_block(ticket)}",
                   ticket.id)
    return Email(to, f"[Ticket #{ticket.id}] Atribuído a você: {ticket.title}", body)


def status_changed(ticket: Ticket, old_status: str, by: User) -> Email:
    to = _recipients([ticket.creator, ticket.assignee], exclude=by)
    body = _layout("Status do ticket alterado",
                   f"<p>{html.escape(by.full_name)} alterou o status de "
                   f"<strong>{html.escape(old_status)}</strong> para "
                   f"<strong>{html.escape(ticket.status.value)}</strong>.</p>{_ticket_block(ticket)}",
                   ticket.id)
    return Email(to, f"[Ticket #{ticket.id}] Status: {old_status} -> {ticket.status.value}", body)


def comment_added(ticket: Ticket, content: str, is_internal: bool, by: User) -> Email:
    # Internal notes are never e-mailed to the client who opened the ticket
    people = [ticket.assignee] if is_internal else [ticket.creator, ticket.assignee]
    to = _recipients(people, exclude=by)
    preview = html.escape(content[:500]).replace("\n", "<br>")
    body = _layout("Novo comentário",
                   f"<p>{html.escape(by.full_name)} comentou:</p>"
                   f'<blockquote style="border-left:3px solid #6c5ce7;margin:0;padding-left:12px">'
                   f"{preview}</blockquote>"
                   f"{_ticket_block(ticket)}", ticket.id)
    return Email(to, f"[Ticket #{ticket.id}] Novo comentário: {ticket.title}", body)


def sla_warning(ticket: Ticket, time_left: str) -> Email:
    to = _recipients([ticket.assignee])
    body = _layout("Alerta de SLA",
                   f"<p>O prazo de SLA deste ticket vence em <strong>{html.escape(time_left)}</strong>.</p>"
                   f"{_ticket_block(ticket)}", ticket.id)
    return Email(to, f"[SLA] Ticket #{ticket.id} vence em {time_left}", body)


def sla_breach(ticket: Ticket, staff: Iterable[User]) -> Email:
    to = _recipients([ticket.assignee, *staff])
    body = _layout("SLA violado", f"<p>O prazo de SLA deste ticket expirou.</p>{_ticket_block(ticket)}", ticket.id)
    return Email(to, f"[SLA VIOLADO] Ticket #{ticket.id}: {ticket.title}", body)
