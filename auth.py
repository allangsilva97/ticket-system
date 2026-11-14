from datetime import timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from config import settings
from database import get_db, utcnow
from models import User, UserRole, TicketStatus

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

# ============ PASSWORD UTILS ============

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# ============ JWT UTILS ============

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    # python-jose rejects a non-string "sub" claim on decode
    if "sub" in to_encode:
        to_encode["sub"] = str(to_encode["sub"])
    if expires_delta:
        expire = utcnow() + expires_delta
    else:
        expire = utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

# ============ USER AUTH ============

def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(token)
    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        raise credentials_exception
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user

def get_optional_user(
    token: Optional[str] = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Returns the logged user if a valid token was sent, otherwise None."""
    if not token:
        return None
    return get_current_user(token, db)

def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

# ============ ROLE DEPENDENCIES ============

def require_admin(current_user: User = Depends(get_current_active_user)) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

def require_agent_or_admin(current_user: User = Depends(get_current_active_user)) -> User:
    if current_user.role not in [UserRole.ADMIN, UserRole.AGENT]:
        raise HTTPException(status_code=403, detail="Agent or Admin access required")
    return current_user

def require_company_access(
    company_id: int,
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Ensure user can access company (admin or same company)"""
    if current_user.role == UserRole.ADMIN:
        return current_user
    if current_user.company_id != company_id:
        raise HTTPException(status_code=403, detail="Access denied to this company")
    return current_user

# ============ TICKET ACCESS CONTROL ============

def can_view_ticket(ticket, current_user: User) -> bool:
    """Check if user can view a ticket"""
    if current_user.role == UserRole.ADMIN:
        return True
    if current_user.role == UserRole.AGENT:
        return ticket.assignee_id == current_user.id or ticket.company_id == current_user.company_id
    if current_user.role == UserRole.CLIENT:
        return ticket.company_id == current_user.company_id
    return False

def can_edit_ticket(ticket, current_user: User) -> bool:
    """Check if user can edit a ticket"""
    if current_user.role == UserRole.ADMIN:
        return True
    if current_user.role == UserRole.AGENT:
        return ticket.assignee_id == current_user.id or ticket.company_id == current_user.company_id
    if current_user.role == UserRole.CLIENT:
        editable = (TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.WAITING_CUSTOMER)
        return ticket.creator_id == current_user.id and ticket.status in editable
    return False

def can_assign_ticket(current_user: User) -> bool:
    """Check if user can assign tickets"""
    return current_user.role in [UserRole.ADMIN, UserRole.AGENT]
