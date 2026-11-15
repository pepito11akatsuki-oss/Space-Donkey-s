from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentPrincipal, get_current_principal, get_tenant_db, require_roles
from app.core.security import hash_password

router = APIRouter(tags=["Organizaciones y Usuarios"])

UserRole = Literal["owner", "agronomist", "viewer"]


class OrganizationOut(BaseModel):
    id: UUID
    name: str
    created_at: datetime


class UserOut(BaseModel):
    id: UUID
    org_id: UUID
    email: str
    full_name: str
    role: str
    created_at: datetime


class CreateOrgUserRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    full_name: str = Field(min_length=2, max_length=120)
    role: UserRole = "agronomist"


class UpdateOrgUserRoleRequest(BaseModel):
    role: UserRole


@router.get("/organizations/me", response_model=OrganizationOut)
async def get_my_organization(db: AsyncSession = Depends(get_tenant_db)):
    row = (
        await db.execute(
            text("SELECT id, name, created_at FROM organizations LIMIT 1")
        )
    ).first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organización no encontrada",
        )
    return OrganizationOut(**row._mapping)


@router.get("/users/me", response_model=UserOut)
async def get_my_profile(
    principal: CurrentPrincipal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_tenant_db),
):
    row = (
        await db.execute(
            text("""
                SELECT id, org_id, email, full_name, role, created_at
                FROM users
                WHERE id = :uid
            """),
            {"uid": principal.user_id},
        )
    ).first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )
    return UserOut(**row._mapping)


@router.get("/users", response_model=list[UserOut])
async def list_organization_users(db: AsyncSession = Depends(get_tenant_db)):
    rows = (
        await db.execute(
            text("""
                SELECT id, org_id, email, full_name, role, created_at
                FROM users
                ORDER BY created_at ASC
            """)
        )
    ).all()
    return [UserOut(**r._mapping) for r in rows]


@router.post(
    "/users",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_organization_user(
    body: CreateOrgUserRequest,
    principal: CurrentPrincipal = Depends(require_roles("owner")),
    db: AsyncSession = Depends(get_tenant_db),
):
    pwd_hash = hash_password(body.password)
    try:
        row = (
            await db.execute(
                text("""
                    INSERT INTO users (org_id, email, password_hash, full_name, role)
                    VALUES (:oid, :email, :pwd, :name, :role)
                    RETURNING id, org_id, email, full_name, role, created_at
                """),
                {
                    "oid": principal.org_id,
                    "email": body.email,
                    "pwd": pwd_hash,
                    "name": body.full_name.strip(),
                    "role": body.role,
                },
            )
        ).one()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El correo ya está registrado en la plataforma",
        )
    return UserOut(**row._mapping)


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_organization_user_role(
    user_id: UUID,
    body: UpdateOrgUserRoleRequest,
    principal: CurrentPrincipal = Depends(require_roles("owner")),
    db: AsyncSession = Depends(get_tenant_db),
):
    if user_id == principal.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes cambiar tu propio rol de owner",
        )

    row = (
        await db.execute(
            text("""
                UPDATE users
                SET role = :role
                WHERE id = :uid
                RETURNING id, org_id, email, full_name, role, created_at
            """),
            {"uid": user_id, "role": body.role},
        )
    ).first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado en tu organización",
        )
    return UserOut(**row._mapping)
