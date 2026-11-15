from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import get_tenant_session

bearer_scheme = HTTPBearer(auto_error=True)


@dataclass(frozen=True)
class CurrentPrincipal:
    user_id: UUID
    org_id: UUID
    role: str


async def get_current_principal(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> CurrentPrincipal:
    try:
        payload = decode_access_token(credentials.credentials)
        return CurrentPrincipal(
            user_id=UUID(payload["sub"]),
            org_id=UUID(payload["org_id"]),
            role=payload["role"],
        )
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_tenant_db(
    principal: CurrentPrincipal = Depends(get_current_principal),
) -> AsyncGenerator[AsyncSession, None]:
    async for session in get_tenant_session(principal.org_id):
        yield session


def require_roles(*allowed_roles: str) -> Callable:
    async def _guard(
        principal: CurrentPrincipal = Depends(get_current_principal),
    ) -> CurrentPrincipal:
        if principal.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permisos insuficientes para el rol '{principal.role}'",
            )
        return principal

    return _guard
