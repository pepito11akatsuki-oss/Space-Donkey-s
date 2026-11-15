from collections.abc import AsyncGenerator
from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.config import settings
from app.core.security import CurrentUser, get_current_user

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=15,
    max_overflow=10,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db(
    current_user: CurrentUser = Depends(get_current_user),
) -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(
                text("SELECT set_config('app.org_id', :org_id, true)"),
                {"org_id": str(current_user.org_id)},
            )
            yield session