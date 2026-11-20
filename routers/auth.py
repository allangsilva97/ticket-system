import time
from collections import defaultdict, deque
from datetime import timedelta
from threading import Lock
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from database import get_db, utcnow
from models import User, UserRole, Company, Ticket, TicketComment, AuditAction, AuditEntityType
from schemas import (
    UserCreate, User as UserSchema, UserUpdate, UserSelfUpdate, Token, UserPasswordUpdate
)
from auth import (
    authenticate_user, create_access_token, get_password_hash, verify_password,
    get_current_active_user, get_optional_user, require_admin,
)
from config import settings
from services import audit_service as audit
from utils import client_ip

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def _check_company(db: Session, company_id: Optional[int]):
    if company_id is not None and not db.query(Company).filter(Company.id == company_id).first():
        raise HTTPException(status_code=400, detail="Company not found")


@router.post("/register", response_model=UserSchema, status_code=201)
def register(
    user_data: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """
    Bootstrap: the very first user is created as admin without authentication.
    After that only admins can create users (otherwise anyone could self-register as admin).
    """
    user_count = db.query(User).count()
    if user_count > 0:
        if current_user is None:
            raise HTTPException(status_code=401, detail="Not authenticated",
                                headers={"WWW-Authenticate": "Bearer"})
        if current_user.role != UserRole.ADMIN or not current_user.is_active:
            raise HTTPException(status_code=403, detail="Admin access required")

    email = user_data.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    role = UserRole.ADMIN if user_count == 0 else user_data.role
    company_id = user_data.company_id if role != UserRole.ADMIN else None
    _check_company(db, company_id)

    user = User(
        email=email,
        hashed_password=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        role=role,
        language=user_data.language,
        company_id=company_id,
    )
    db.add(user)
    db.flush()
    audit.log(db, AuditEntityType.USER, user.id, AuditAction.CREATE, current_user or user,
              changes=audit.snapshot(user, audit.USER_FIELDS), request=request)
    db.commit()
    db.refresh(user)
    return user


# ============ Login brute-force protection ============
# In-memory, per process: enough for a single uvicorn worker. With several
# workers/servers, move this to a shared store (e.g. Redis).

LOGIN_WINDOW_SECONDS = 15 * 60
MAX_FAILURES_PER_ACCOUNT = 5   # per (ip, email)
MAX_FAILURES_PER_IP = 20       # per ip, any email

_failures: dict[tuple, deque] = defaultdict(deque)
_failures_lock = Lock()


def _prune(q: deque, now: float):
    while q and now - q[0] > LOGIN_WINDOW_SECONDS:
        q.popleft()


def _check_login_allowed(ip: str, email: str):
    now = time.monotonic()
    with _failures_lock:
        for key, limit in (((ip, email), MAX_FAILURES_PER_ACCOUNT), ((ip,), MAX_FAILURES_PER_IP)):
            q = _failures.get(key)
            if not q:
                continue
            _prune(q, now)
            if len(q) >= limit:
                retry_after = int(LOGIN_WINDOW_SECONDS - (now - q[0])) + 1
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many failed login attempts. Try again later.",
                    headers={"Retry-After": str(retry_after)},
                )


def _record_login_failure(ip: str, email: str):
    now = time.monotonic()
    with _failures_lock:
        for key in ((ip, email), (ip,)):
            _failures[key].append(now)


def _clear_login_failures(ip: str, email: str):
    with _failures_lock:
        _failures.pop((ip, email), None)


@router.post("/login", response_model=Token)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """Form login (username = email). Works with the frontend and Swagger's Authorize button."""
    email = form_data.username.strip().lower()
    ip = client_ip(request)

    _check_login_allowed(ip, email)
    user = authenticate_user(db, email, form_data.password)
    if not user:
        _record_login_failure(ip, email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    _clear_login_failures(ip, email)

    user.last_login = utcnow()
    audit.log(db, AuditEntityType.USER, user.id, AuditAction.LOGIN, user, request=request)
    db.commit()
    db.refresh(user)

    access_token = create_access_token(
        data={"sub": user.id, "email": user.email, "role": user.role.value},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {"access_token": access_token, "token_type": "bearer", "user": user}


@router.get("/me", response_model=UserSchema)
def get_me(current_user: User = Depends(get_current_active_user)):
    return current_user


@router.put("/me", response_model=UserSchema)
def update_me(
    user_data: UserSelfUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    update_data = user_data.model_dump(exclude_unset=True)
    if update_data.get("email"):
        update_data["email"] = update_data["email"].lower()
        if update_data["email"] != current_user.email and \
                db.query(User).filter(User.email == update_data["email"]).first():
            raise HTTPException(status_code=400, detail="Email already in use")

    for field, value in update_data.items():
        setattr(current_user, field, value)

    db.commit()
    db.refresh(current_user)
    return current_user


@router.put("/me/password")
def change_password(
    password_data: UserPasswordUpdate,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    current_user.hashed_password = get_password_hash(password_data.new_password)
    audit.log(db, AuditEntityType.USER, current_user.id, AuditAction.PASSWORD_CHANGE, current_user,
              request=request)
    db.commit()
    return {"message": "Password updated successfully"}


# ============ Admin-only user management ============

@router.get("/users", response_model=list[UserSchema])
def list_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return db.query(User).offset(skip).limit(limit).all()


@router.get("/users/{user_id}", response_model=UserSchema)
def get_user(user_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/users/{user_id}", response_model=UserSchema)
def update_user(
    user_id: int,
    user_data: UserUpdate,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = user_data.model_dump(exclude_unset=True)

    if update_data.get("email"):
        update_data["email"] = update_data["email"].lower()
        if update_data["email"] != user.email and \
                db.query(User).filter(User.email == update_data["email"]).first():
            raise HTTPException(status_code=400, detail="Email already in use")

    if "company_id" in update_data:
        _check_company(db, update_data["company_id"])

    # Prevent the admin from locking themselves out
    if user.id == current_user.id:
        if update_data.get("role", UserRole.ADMIN) != UserRole.ADMIN or update_data.get("is_active") is False:
            raise HTTPException(status_code=400, detail="You cannot demote or deactivate yourself")

    before = audit.snapshot(user, audit.USER_FIELDS)
    for field, value in update_data.items():
        setattr(user, field, value)

    changes = audit.diff(before, audit.snapshot(user, audit.USER_FIELDS))
    if changes:
        audit.log(db, AuditEntityType.USER, user.id, AuditAction.UPDATE, current_user,
                  changes=changes, request=request)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    has_history = (
        db.query(Ticket).filter((Ticket.creator_id == user_id) | (Ticket.assignee_id == user_id)).first()
        or db.query(TicketComment).filter(TicketComment.author_id == user_id).first()
    )
    if has_history:
        raise HTTPException(status_code=400, detail="User has tickets/comments. Deactivate instead.")

    audit.log(db, AuditEntityType.USER, user.id, AuditAction.DELETE, current_user,
              changes=audit.snapshot(user, audit.USER_FIELDS), request=request)
    db.delete(user)
    db.commit()
