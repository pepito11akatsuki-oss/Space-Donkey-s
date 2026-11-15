from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.alert_repo import AlertRepository


class AlertService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AlertRepository(db)

    async def scan_stale_stakes(self, max_silence_hours: int = 24) -> dict[str, int]:
        q = text("""
            SELECT id, device_uid, parcel_id, last_seen_at
            FROM stakes
            WHERE is_active = true
              AND (last_seen_at IS NULL OR last_seen_at < now() - make_interval(hours => :hours))
        """)
        rows = (await self.db.execute(q, {"hours": max_silence_hours})).mappings().all()
        created = 0
        for s in rows:
            inserted = await self.repo.create_stake_alert(
                stake_id=s["id"],
                parcel_id=s["parcel_id"],
                kind="sin_reporte",
                severity="critica",
                payload={
                    "device_uid": s["device_uid"],
                    "last_seen_at": s["last_seen_at"].isoformat() if s["last_seen_at"] else None,
                    "threshold_hours": max_silence_hours,
                },
            )
            if inserted:
                created += 1
        return {"scanned_stakes": len(rows), "new_alerts_created": created}