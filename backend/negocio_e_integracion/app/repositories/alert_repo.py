import json
from typing import Any
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class AlertRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_alerts(
        self, only_open: bool = True, parcel_id: UUID | None = None
    ) -> list[dict[str, Any]]:
        conditions = []
        params: dict[str, Any] = {}
        if only_open:
            conditions.append("a.resolved_at IS NULL")
        if parcel_id:
            conditions.append("(a.parcel_id = :parcel_id OR s.parcel_id = :parcel_id)")
            params["parcel_id"] = parcel_id
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        q = text(f"""
            SELECT a.id, a.stake_id, s.device_uid,
                   COALESCE(a.parcel_id, s.parcel_id) AS parcel_id,
                   a.kind, a.severity, a.payload, a.created_at, a.resolved_at
            FROM alerts a
            LEFT JOIN stakes s ON s.id = a.stake_id
            {where}
            ORDER BY a.created_at DESC
        """)
        return [dict(r) for r in (await self.db.execute(q, params)).mappings().all()]

    async def resolve(self, alert_id: UUID) -> dict[str, Any] | None:
        q = text("""
            UPDATE alerts
            SET resolved_at = COALESCE(resolved_at, now())
            WHERE id = :alert_id
            RETURNING id, stake_id, parcel_id, kind, severity, resolved_at
        """)
        row = (await self.db.execute(q, {"alert_id": alert_id})).mappings().first()
        return dict(row) if row else None

    async def create_stake_alert(
        self,
        stake_id: UUID,
        parcel_id: UUID | None,
        kind: str,
        severity: str,
        payload: dict[str, Any],
    ) -> bool:
        q = text("""
            INSERT INTO alerts (stake_id, parcel_id, kind, severity, payload)
            VALUES (:stake_id, :parcel_id, :kind, :severity, CAST(:payload AS jsonb))
            ON CONFLICT (stake_id, kind)
            WHERE resolved_at IS NULL AND stake_id IS NOT NULL
            DO NOTHING
            RETURNING id
        """)
        res = await self.db.execute(
            q,
            {
                "stake_id": stake_id,
                "parcel_id": parcel_id,
                "kind": kind,
                "severity": severity,
                "payload": json.dumps(payload),
            },
        )
        return res.first() is not None