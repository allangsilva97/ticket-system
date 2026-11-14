import enum
import secrets

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum as SQLEnum, Boolean, Index, JSON
from sqlalchemy.orm import relationship

from database import Base, utcnow

# ============ ENUMS ============

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    AGENT = "agent"
    CLIENT = "client"

class TicketStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING_CUSTOMER = "waiting_customer"
    WAITING_THIRD_PARTY = "waiting_third_party"
    CLOSED = "closed"
    CANCELLED = "cancelled"

class TicketPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"
    CRITICAL = "critical"

class AuditAction(str, enum.Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    STATUS_CHANGE = "status_change"
    ASSIGNMENT = "assignment"
    COMMENT_ADD = "comment_add"
    COMMENT_DELETE = "comment_delete"
    ATTACHMENT_UPLOAD = "attachment_upload"
    ATTACHMENT_DELETE = "attachment_delete"
    LOGIN = "login"
    PASSWORD_CHANGE = "password_change"

class AuditEntityType(str, enum.Enum):
    TICKET = "ticket"
    COMPANY = "company"
    USER = "user"
    COMMENT = "comment"
    ATTACHMENT = "attachment"

class TicketCategory(str, enum.Enum):
    TECHNICAL = "technical"
    BILLING = "billing"
    FEATURE_REQUEST = "feature_request"
    BUG_REPORT = "bug_report"
    GENERAL_INQUIRY = "general_inquiry"
    ACCESS_REQUEST = "access_request"
    SECURITY = "security"
    OTHER = "other"

# Unambiguous alphabet (no 0/O, 1/I/L) - the code is typed by people
TRACKING_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
TRACKING_CODE_LENGTH = 10


def generate_tracking_code() -> str:
    """Random public code used to follow a ticket without logging in.
    31^10 ≈ 8e14 combinations, so codes cannot be enumerated."""
    return "".join(secrets.choice(TRACKING_ALPHABET) for _ in range(TRACKING_CODE_LENGTH))


# ============ MODELS ============

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole), default=UserRole.CLIENT, nullable=False)
    is_active = Column(Boolean, default=True)
    language = Column(String(10), default="en")  # en, pt-BR, es
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    last_login = Column(DateTime, nullable=True)

    # Relationships
    company = relationship("Company", back_populates="users")
    assigned_tickets = relationship("Ticket", foreign_keys="Ticket.assignee_id", back_populates="assignee")
    created_tickets = relationship("Ticket", foreign_keys="Ticket.creator_id", back_populates="creator")
    comments = relationship("TicketComment", back_populates="author")

class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True, nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    address = Column(Text, nullable=True)
    city = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    timezone = Column(String(50), default="UTC")
    sla_hours = Column(Integer, default=24)  # Default SLA in hours
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    # Relationships
    users = relationship("User", back_populates="company")
    tickets = relationship("Ticket", back_populates="company")

class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    tracking_code = Column(String(16), unique=True, index=True, nullable=True, default=generate_tracking_code)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(SQLEnum(TicketStatus), default=TicketStatus.OPEN, nullable=False, index=True)
    priority = Column(SQLEnum(TicketPriority), default=TicketPriority.MEDIUM, nullable=False, index=True)
    category = Column(SQLEnum(TicketCategory), default=TicketCategory.GENERAL_INQUIRY, nullable=False, index=True)

    # Foreign keys
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    assignee_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    # SLA Tracking
    sla_due_at = Column(DateTime, nullable=True)
    first_response_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    # SLA notifications already sent (avoid e-mailing the same alert every check)
    sla_warning_notified_at = Column(DateTime, nullable=True)
    sla_breach_notified_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=utcnow, index=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    closed_at = Column(DateTime, nullable=True)

    # Relationships
    company = relationship("Company", back_populates="tickets")
    creator = relationship("User", foreign_keys=[creator_id], back_populates="created_tickets")
    assignee = relationship("User", foreign_keys=[assignee_id], back_populates="assigned_tickets")
    comments = relationship("TicketComment", back_populates="ticket", cascade="all, delete-orphan")
    attachments = relationship("TicketAttachment", back_populates="ticket", cascade="all, delete-orphan")

    # Indexes for common queries
    __table_args__ = (
        Index('ix_tickets_company_status', 'company_id', 'status'),
        Index('ix_tickets_assignee_status', 'assignee_id', 'status'),
        Index('ix_tickets_created_priority', 'created_at', 'priority'),
    )

class TicketComment(Base):
    __tablename__ = "ticket_comments"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False, index=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    is_internal = Column(Boolean, default=False)  # Internal notes vs customer-visible
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    ticket = relationship("Ticket", back_populates="comments")
    author = relationship("User", back_populates="comments")

class TicketAttachment(Base):
    __tablename__ = "ticket_attachments"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=True)
    file_size = Column(Integer, nullable=False)
    file_path = Column(String(500), nullable=False)  # Relative path
    uploaded_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=utcnow)

    ticket = relationship("Ticket", back_populates="attachments")
    uploaded_by = relationship("User")


class AuditLog(Base):
    """Immutable history of who changed what. Rows are never updated."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(SQLEnum(AuditEntityType), nullable=False, index=True)
    entity_id = Column(Integer, nullable=False, index=True)
    action = Column(SQLEnum(AuditAction), nullable=False, index=True)
    # {"field": {"old": ..., "new": ...}} for updates, a snapshot for create/delete
    changes = Column(JSON, nullable=True)
    description = Column(Text, nullable=True)

    # Denormalised on purpose: the log must survive the user being deleted
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    user_name = Column(String(255), nullable=True)
    user_role = Column(String(50), nullable=True)
    ip_address = Column(String(45), nullable=True)

    created_at = Column(DateTime, default=utcnow, index=True)

    __table_args__ = (
        Index("ix_audit_entity", "entity_type", "entity_id"),
    )
