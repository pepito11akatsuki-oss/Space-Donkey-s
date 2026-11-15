import asyncio
import sys
from collections.abc import AsyncGenerator
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_public_db() -> AsyncGenerator[AsyncSession, None]:
    """Sesión sin tenant fijado (para auth inicial y catálogos de solo lectura)."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            yield session


async def get_tenant_session(org_id: UUID) -> AsyncGenerator[AsyncSession, None]:
    """Fija app.org_id localmente en la transacción para activar Row-Level Security."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(
                text("SELECT set_config('app.org_id', :org_id, true)"),
                {"org_id": str(org_id)},
            )
            yield session
