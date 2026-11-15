import json
from typing import Any
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class ClimateRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_cell_by_id(self, cell_id: UUID) -> dict[str, Any] | None:
        q = text("SELECT id, source, center_lat, center_lon FROM climate_cells WHERE id = :id")
        row = (await self.db.execute(q, {"id": cell_id})).mappings().first()
        return dict(row) if row else None

    async def upsert_weather_daily(self, cell_id: UUID, records: list[dict[str, Any]]) -> int:
        if not records:
            return 0
        q = text("""
            INSERT INTO weather_daily (
                cell_id, obs_date, precip_mm, precip_product,
                air_temp_c, rel_humidity, skin_temp_c,
                soil_wetness_surface, soil_wetness_root, raw_payload, fetched_at
            )
            VALUES (
                :cell_id, :obs_date, :precip_mm, 'merra2_prectotcorr',
                :air_temp_c, :rel_humidity, :skin_temp_c,
                :soil_wetness_surface, :soil_wetness_root, CAST(:raw_payload AS jsonb), now()
            )
            ON CONFLICT (cell_id, obs_date) DO UPDATE SET
                precip_mm = EXCLUDED.precip_mm,
                air_temp_c = EXCLUDED.air_temp_c,
                rel_humidity = EXCLUDED.rel_humidity,
                skin_temp_c = EXCLUDED.skin_temp_c,
                soil_wetness_surface = EXCLUDED.soil_wetness_surface,
                soil_wetness_root = EXCLUDED.soil_wetness_root,
                raw_payload = EXCLUDED.raw_payload,
                fetched_at = now()
        """)
        for rec in records:
            await self.db.execute(
                q,
                {
                    "cell_id": cell_id,
                    "obs_date": rec["obs_date"],
                    "precip_mm": rec["precip_mm"],
                    "air_temp_c": rec["air_temp_c"],
                    "rel_humidity": rec["rel_humidity"],
                    "skin_temp_c": rec["skin_temp_c"],
                    "soil_wetness_surface": rec["soil_wetness_surface"],
                    "soil_wetness_root": rec["soil_wetness_root"],
                    "raw_payload": json.dumps(rec["raw_payload"]),
                },
            )
        return len(records)