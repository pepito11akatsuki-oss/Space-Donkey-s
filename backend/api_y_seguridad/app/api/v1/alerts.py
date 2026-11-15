from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentPrincipal, get_tenant_db, require_roles

router = APIRouter(prefix="/alerts", tags=["Alertas"])


@router.get("")
async def list_alerts(
    only_open: bool = Query(default=True),
    db: AsyncSession = Depends(get_tenant_db),
):
    if only_open:
        rows = (
            await db.execute(
                text("""
                    SELECT id, stake_id, parcel_id, kind, severity, payload,
                           created_at, resolved_at
                    FROM alerts
                    WHERE resolved_at IS NULL
                    ORDER BY created_at DESC
                """)
            )
        ).all()
    else:
        rows = (
            await db.execute(
                text("""
                    SELECT id, stake_id, parcel_id, kind, severity, payload,
                           created_at, resolved_at
                    FROM alerts
                    ORDER BY created_at DESC
                    LIMIT 200
                """)
            )
        ).all()
    return [dict(r._mapping) for r in rows]


@router.patch("/{alert_id}/resolve")
async def resolve_alert(
    alert_id: UUID,
    principal: CurrentPrincipal = Depends(require_roles("owner", "agronomist")),
    db: AsyncSession = Depends(get_tenant_db),
):
    row = (
        await db.execute(
            text("""
                UPDATE alerts
                SET resolved_at = now()
                WHERE id = :aid AND resolved_at IS NULL
                RETURNING id, stake_id, parcel_id, kind, severity, payload,
                          created_at, resolved_at
            """),
            {"aid": alert_id},
        )
    ).first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alerta no encontrada o ya estaba resuelta",
        )
    return dict(row._mapping)
