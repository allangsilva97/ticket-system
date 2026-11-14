from math import ceil
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models import Company, User, Ticket, UserRole, AuditAction, AuditEntityType
from schemas import (
    CompanyCreate, CompanyUpdate, Company as CompanySchema, CompanyList, PaginatedResponse
)
from auth import get_current_active_user, require_admin
from services import audit_service as audit

router = APIRouter(prefix="/api/companies", tags=["Companies"])


def _counts(db: Session, company_id: int):
    ticket_count = db.query(func.count(Ticket.id)).filter(Ticket.company_id == company_id).scalar() or 0
    user_count = db.query(func.count(User.id)).filter(User.company_id == company_id).scalar() or 0
    return ticket_count, user_count


def _to_schema(db: Session, company: Company) -> CompanySchema:
    schema = CompanySchema.model_validate(company)
    schema.ticket_count, schema.user_count = _counts(db, company.id)
    return schema


@router.post("", response_model=CompanySchema, status_code=201)
def create_company(
    company_data: CompanyCreate,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if db.query(Company).filter(Company.name == company_data.name).first():
        raise HTTPException(status_code=400, detail="Company name already exists")

    company = Company(**company_data.model_dump())
    db.add(company)
    db.flush()
    audit.log(db, AuditEntityType.COMPANY, company.id, AuditAction.CREATE, current_user,
              changes=audit.snapshot(company, audit.COMPANY_FIELDS), request=request)
    db.commit()
    db.refresh(company)
    return _to_schema(db, company)


@router.get("", response_model=PaginatedResponse)
def list_companies(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    query = db.query(Company)

    # Non-admins only see their own company (clients need it for the ticket form)
    if current_user.role != UserRole.ADMIN:
        query = query.filter(Company.id == current_user.company_id)

    if search:
        query = query.filter(Company.name.ilike(f"%{search}%"))
    if is_active is not None:
        query = query.filter(Company.is_active == is_active)

    total = query.count()
    companies = query.order_by(Company.name).offset((page - 1) * page_size).limit(page_size).all()

    result = []
    for c in companies:
        ticket_count, user_count = _counts(db, c.id)
        result.append(CompanyList(
            id=c.id, name=c.name, email=c.email, phone=c.phone,
            city=c.city, country=c.country, is_active=c.is_active,
            ticket_count=ticket_count, user_count=user_count,
            created_at=c.created_at,
        ))

    return PaginatedResponse(
        items=result, total=total, page=page, page_size=page_size,
        total_pages=ceil(total / page_size) if total else 0,
    )


@router.get("/{company_id}", response_model=CompanySchema)
def get_company(
    company_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if current_user.role != UserRole.ADMIN and current_user.company_id != company_id:
        raise HTTPException(status_code=403, detail="Access denied")

    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return _to_schema(db, company)


@router.put("/{company_id}", response_model=CompanySchema)
def update_company(
    company_id: int,
    company_data: CompanyUpdate,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    if company_data.name and company_data.name != company.name:
        if db.query(Company).filter(Company.name == company_data.name).first():
            raise HTTPException(status_code=400, detail="Company name already exists")

    before = audit.snapshot(company, audit.COMPANY_FIELDS)
    for field, value in company_data.model_dump(exclude_unset=True).items():
        setattr(company, field, value)

    changes = audit.diff(before, audit.snapshot(company, audit.COMPANY_FIELDS))
    if changes:
        audit.log(db, AuditEntityType.COMPANY, company.id, AuditAction.UPDATE, current_user,
                  changes=changes, request=request)
    db.commit()
    db.refresh(company)
    return _to_schema(db, company)


@router.delete("/{company_id}", status_code=204)
def delete_company(
    company_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    ticket_count, user_count = _counts(db, company_id)
    if ticket_count > 0 or user_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete company with {ticket_count} tickets and {user_count} users. Deactivate instead.",
        )

    audit.log(db, AuditEntityType.COMPANY, company.id, AuditAction.DELETE, current_user,
              changes=audit.snapshot(company, audit.COMPANY_FIELDS), request=request)
    db.delete(company)
    db.commit()
