from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import register_exception_handlers
from app.core.security import CurrentUser, get_current_user

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Backend de negocio e integración para AgroStake (Hacka-NASA 2026).",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)
app.include_router(api_router)


@app.get("/health", tags=["Sistema"])
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": settings.APP_NAME}


@app.get("/api/v1/context", tags=["Sistema"])
async def verify_tenant_context(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_row = (
        await db.execute(text("SELECT id, name, created_at FROM organizations"))
    ).mappings().first()

    return {
        "user_id": str(current_user.user_id),
        "org_id": str(current_user.org_id),
        "role": current_user.role,
        "organization": dict(org_row) if org_row else None,
    }