from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentPrincipal, get_current_principal, get_tenant_db
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.db.session import get_public_db

router = APIRouter(prefix="/auth", tags=["Autenticación"])


class RegisterRequest(BaseModel):
    organization_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    full_name: str = Field(min_length=2, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=20)


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    org_id: UUID
    user_id: UUID
    role: str


@router.post(
    "/register",
    response_model=TokenPairResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    body: RegisterRequest, db: AsyncSession = Depends(get_public_db)
):
    pwd_hash = hash_password(body.password)
    try:
        row = (
            await db.execute(
                text(
                    "SELECT org_id, user_id FROM auth_register_owner(:org, :email, :pwd, :name)"
                ),
                {
                    "org": body.organization_name.strip(),
                    "email": body.email,
                    "pwd": pwd_hash,
                    "name": body.full_name.strip(),
                },
            )
        ).one()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El correo ya está registrado",
        )

    raw_refresh, refresh_hash, expires_at = generate_refresh_token()
    await db.execute(
        text("SELECT set_config('app.org_id', :oid, true)"),
        {"oid": str(row.org_id)},
    )
    await db.execute(
        text(
            "INSERT INTO refresh_tokens (user_id, token_hash, expires_at) VALUES (:uid, :th, :exp)"
        ),
        {"uid": row.user_id, "th": refresh_hash, "exp": expires_at},
    )

    return TokenPairResponse(
        access_token=create_access_token(row.user_id, row.org_id, "owner"),
        refresh_token=raw_refresh,
        org_id=row.org_id,
        user_id=row.user_id,
        role="owner",
    )


@router.post("/login", response_model=TokenPairResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_public_db)):
    user = (
        await db.execute(
            text(
                "SELECT id, org_id, password_hash, role FROM auth_get_user_by_email(:email)"
            ),
            {"email": body.email},
        )
    ).first()

    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
        )

    raw_refresh, refresh_hash, expires_at = generate_refresh_token()
    await db.execute(
        text("SELECT set_config('app.org_id', :oid, true)"),
        {"oid": str(user.org_id)},
    )
    await db.execute(
        text(
            "INSERT INTO refresh_tokens (user_id, token_hash, expires_at) VALUES (:uid, :th, :exp)"
        ),
        {"uid": user.id, "th": refresh_hash, "exp": expires_at},
    )

    return TokenPairResponse(
        access_token=create_access_token(user.id, user.org_id, user.role),
        refresh_token=raw_refresh,
        org_id=user.org_id,
        user_id=user.id,
        role=user.role,
    )


@router.post("/refresh", response_model=TokenPairResponse)
async def refresh_session(
    body: RefreshRequest, db: AsyncSession = Depends(get_public_db)
):
    rec = (
        await db.execute(
            text("SELECT * FROM auth_lookup_refresh_token(:th)"),
            {"th": hash_token(body.refresh_token)},
        )
    ).first()

    now = datetime.now(timezone.utc)
    if not rec or rec.revoked_at is not None or rec.expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido, revocado o expirado",
        )

    await db.execute(
        text("SELECT set_config('app.org_id', :oid, true)"),
        {"oid": str(rec.org_id)},
    )
    await db.execute(
        text("UPDATE refresh_tokens SET revoked_at = now() WHERE id = :tid"),
        {"tid": rec.token_id},
    )

    new_raw, new_hash, new_exp = generate_refresh_token()
    await db.execute(
        text(
            "INSERT INTO refresh_tokens (user_id, token_hash, expires_at) VALUES (:uid, :th, :exp)"
        ),
        {"uid": rec.user_id, "th": new_hash, "exp": new_exp},
    )

    return TokenPairResponse(
        access_token=create_access_token(rec.user_id, rec.org_id, rec.role),
        refresh_token=new_raw,
        org_id=rec.org_id,
        user_id=rec.user_id,
        role=rec.role,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: RefreshRequest,
    principal: CurrentPrincipal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_tenant_db),
):
    await db.execute(
        text("""
            UPDATE refresh_tokens
            SET revoked_at = now()
            WHERE user_id = :uid AND token_hash = :th AND revoked_at IS NULL
        """),
        {"uid": principal.user_id, "th": hash_token(body.refresh_token)},
    )
