import email_validator
from pydantic import BaseModel, EmailStr, Field, ConfigDict

# email-validator rejects special-use domains such as ".local" by default, but
# intranet / Active Directory addresses (and the default admin@ticketsystem.local)
# use it. Without this, any user with such an email could log in but every
# profile/user update would fail with 422.
if "local" in email_validator.SPECIAL_USE_DOMAIN_NAMES:
    email_validator.SPECIAL_USE_DOMAIN_NAMES.remove("local")
from typing import Optional, List, Any, Literal
from datetime import datetime
from models import UserRole, TicketStatus, TicketPriority, TicketCategory

# ============ USER SCHEMAS ============

class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    role: UserRole = UserRole.CLIENT
    language: Literal["en", "pt-BR", "es"] = "en"
    company_id: Optional[int] = None

class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=100)

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    language: Optional[Literal["en", "pt-BR", "es"]] = None
    company_id: Optional[int] = None
    is_active: Optional[bool] = None

class UserSelfUpdate(BaseModel):
    """Fields a user may change on their own profile (no role/company/is_active escalation)."""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    language: Optional[Literal["en", "pt-BR", "es"]] = None

class UserPasswordUpdate(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=100)

class User(UserBase):
    email: str  # do not re-validate stored emails on output
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    company: Optional["Company"] = None

    model_config = ConfigDict(from_attributes=True)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: User

# ============ COMPANY SCHEMAS ============

class CompanyBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    timezone: Optional[str] = "UTC"
    sla_hours: int = Field(default=24, ge=1, le=720)

class CompanyCreate(CompanyBase):
    pass

class CompanyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    timezone: Optional[str] = None
    sla_hours: Optional[int] = Field(None, ge=1, le=720)
    is_active: Optional[bool] = None

class Company(CompanyBase):
    email: Optional[str] = None
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    ticket_count: int = 0
    user_count: int = 0

    model_config = ConfigDict(from_attributes=True)

class CompanyList(BaseModel):
    id: int
    name: str
    email: Optional[str]
    phone: Optional[str]
    city: Optional[str]
    country: Optional[str]
    is_active: bool
    ticket_count: int = 0
    user_count: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# ============ TICKET SCHEMAS ============

class TicketBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    priority: TicketPriority = TicketPriority.MEDIUM
    category: TicketCategory = TicketCategory.GENERAL_INQUIRY
    company_id: int
    assignee_id: Optional[int] = None

class TicketCreate(TicketBase):
    pass

class TicketUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[TicketStatus] = None
    priority: Optional[TicketPriority] = None
    category: Optional[TicketCategory] = None
    assignee_id: Optional[int] = None

class TicketStatusUpdate(BaseModel):
    status: TicketStatus

class TicketAssignment(BaseModel):
    assignee_id: Optional[int] = None

class Ticket(TicketBase):
    id: int
    tracking_code: Optional[str] = None
    status: TicketStatus
    creator_id: int
    assignee_id: Optional[int] = None
    sla_due_at: Optional[datetime] = None
    first_response_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None
    company: CompanyList
    creator: User
    assignee: Optional[User] = None
    comment_count: int = 0
    attachment_count: int = 0
    is_overdue: bool = False

    model_config = ConfigDict(from_attributes=True)

class TicketList(BaseModel):
    id: int
    tracking_code: Optional[str] = None
    title: str
    status: TicketStatus
    priority: TicketPriority
    category: TicketCategory
    company_name: str
    company_id: int
    assignee_name: Optional[str] = None
    assignee_id: Optional[int] = None
    creator_name: str
    created_at: datetime
    updated_at: datetime
    sla_due_at: Optional[datetime] = None
    is_overdue: bool = False

    model_config = ConfigDict(from_attributes=True)

# ============ COMMENT SCHEMAS ============

class CommentBase(BaseModel):
    content: str = Field(..., min_length=1)
    is_internal: bool = False

class CommentCreate(CommentBase):
    pass

class CommentUpdate(BaseModel):
    content: Optional[str] = Field(None, min_length=1)
    is_internal: Optional[bool] = None

class Comment(CommentBase):
    id: int
    ticket_id: int
    author_id: int
    author_name: str
    author_role: UserRole
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

# ============ ATTACHMENT SCHEMAS ============

class AttachmentBase(BaseModel):
    filename: str
    original_filename: str
    content_type: Optional[str] = None
    file_size: int
    file_path: str

class Attachment(AttachmentBase):
    id: int
    ticket_id: int
    uploaded_by_id: int
    uploaded_by_name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# ============ DASHBOARD/STATS ============

class DashboardStats(BaseModel):
    total_tickets: int
    open_tickets: int
    in_progress_tickets: int
    waiting_tickets: int
    closed_tickets: int
    overdue_tickets: int
    total_companies: int
    total_users: int
    tickets_by_status: dict
    tickets_by_priority: dict
    tickets_by_category: dict
    recent_tickets: List[TicketList]
    my_assigned_tickets: List[TicketList]  # For agents

class PaginatedResponse(BaseModel):
    # Any => serialized with the runtime type (List[BaseModel] would serialize every item as {})
    items: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int

# ============ FILTER SCHEMAS ============

class TicketFilters(BaseModel):
    status: Optional[TicketStatus] = None
    priority: Optional[TicketPriority] = None
    category: Optional[TicketCategory] = None
    company_id: Optional[int] = None
    assignee_id: Optional[int] = None
    creator_id: Optional[int] = None
    search: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    overdue_only: bool = False
    page: int = 1
    page_size: int = 20

# Forward references
User.model_rebuild()
Company.model_rebuild()
Ticket.model_rebuild()
