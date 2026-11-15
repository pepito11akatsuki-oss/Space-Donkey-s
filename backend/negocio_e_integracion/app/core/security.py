from dataclasses import dataclass
from typing import Literal
from uuid import UUID
import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.core.config import settings
from app.core.exceptions import ForbiddenError

UserRole = Literal["owner", "agronomist", "viewer"]
bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    user_id: UUID
    org_id: UUID
    role: UserRole


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    x_dev_org_id: str | None = Header(default=None),
    x_dev_user_id: str | None = Header(default=None),
    x_dev_role: UserRole = Header(default="owner"),
) -> CurrentUser:
    if credentials is not None:
        try:
            payload = jwt.decode(
                credentials.credentials,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
            )
            return CurrentUser(
                user_id=UUID(payload["sub"]),
                org_id=UUID(payload["org_id"]),
                role=payload.get("role", "viewer"),
            )
        except (jwt.PyJWTError, KeyError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token JWT inválido o expirado.",
            ) from exc

    if settings.ENVIRONMENT == "development" and x_dev_org_id and x_dev_user_id:
        try:
            return CurrentUser(
                user_id=UUID(x_dev_user_id),
                org_id=UUID(x_dev_org_id),
                role=x_dev_role,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Headers X-Dev-Org-Id / X-Dev-User-Id deben ser UUID válidos.",
            ) from exc

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Se requiere autenticación Bearer JWT.",
    )


def require_write_role(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role not in ("owner", "agronomist"):
        raise ForbiddenError("El rol 'viewer' solo tiene permisos de lectura.")
    return user