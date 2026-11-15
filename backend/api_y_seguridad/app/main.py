from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1 import (
    alerts,
    auth,
    catalogs,
    measurements,
    parcels,
    recommendations,
    stakes_iot,
    users_orgs,
)
from app.core.config import settings
from app.db.session import get_public_db

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="API REST Multi-Tenant de AgroStake (PostgreSQL v3.3 + RLS)",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["Sistema"])
async def health_check(db: AsyncSession = Depends(get_public_db)):
    row = (
        await db.execute(
            text("SELECT current_user AS db_user, current_database() AS db_name")
        )
    ).one()
    return {
        "status": "ok",
        "db_user": row.db_user,
        "db_name": row.db_name,
    }


app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(users_orgs.router, prefix=settings.API_V1_PREFIX)
app.include_router(catalogs.router, prefix=settings.API_V1_PREFIX)
app.include_router(parcels.router, prefix=settings.API_V1_PREFIX)
app.include_router(stakes_iot.router, prefix=settings.API_V1_PREFIX)
app.include_router(measurements.router, prefix=settings.API_V1_PREFIX)
app.include_router(recommendations.router, prefix=settings.API_V1_PREFIX)
app.include_router(alerts.router, prefix=settings.API_V1_PREFIX)
