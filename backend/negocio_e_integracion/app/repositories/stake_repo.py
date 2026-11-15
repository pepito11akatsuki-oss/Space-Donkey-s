from typing import Any
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class StakeRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_stakes(self, parcel_id: UUID | None = None) -> list[dict[str, Any]]:
        where = "WHERE s.parcel_id = :parcel_id" if parcel_id else ""
        q = text(f"""
            SELECT s.id, s.device_uid, s.parcel_id, p.name AS parcel_name,
                   s.firmware_version, s.last_transport, s.last_seen_at,
                   s.installed_at, s.is_active
            FROM stakes s
            LEFT JOIN parcels p ON p.id = s.parcel_id
            {where}
            ORDER BY s.device_uid
        """)
        params = {"parcel_id": parcel_id} if parcel_id else {}
        return [dict(r) for r in (await self.db.execute(q, params)).mappings().all()]

    async def link_to_parcel(self, stake_id: UUID, parcel_id: UUID | None) -> dict[str, Any] | None:
        q = text("""
            UPDATE stakes
            SET parcel_id = :parcel_id,
                installed_at = CASE WHEN :parcel_id IS NOT NULL THEN COALESCE(installed_at, now()) ELSE installed_at END
            WHERE id = :stake_id
            RETURNING id, device_uid, parcel_id, last_transport, last_seen_at, installed_at, is_active
        """)
        row = (
            await self.db.execute(q, {"stake_id": stake_id, "parcel_id": parcel_id})
        ).mappings().first()
        return dict(row) if row else None

    async def get_readings(self, stake_id: UUID, limit: int = 100) -> list[dict[str, Any]]:
        q = text("""
            SELECT id, measured_at, received_at, transport,
                   soil_temperature_c, soil_moisture_raw, soil_moisture_pct,
                   battery_v, is_simulated
            FROM soil_readings
            WHERE stake_id = :stake_id
            ORDER BY measured_at DESC
            LIMIT :limit
        """)
        return [
            dict(r)
            for r in (await self.db.execute(q, {"stake_id": stake_id, "limit": limit})).mappings().all()
        ]