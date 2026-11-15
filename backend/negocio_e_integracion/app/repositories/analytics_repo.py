from datetime import datetime
from typing import Any
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class AnalyticsRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_parcel_summary(self, parcel_id: UUID) -> dict[str, Any] | None:
        parcel_q = text("""
            SELECT id, name, soil_texture, climate_cell_id,
                   latest_weather_date(climate_cell_id) AS latest_weather_dt
            FROM parcels WHERE id = :parcel_id
        """)
        parcel = (await self.db.execute(parcel_q, {"parcel_id": parcel_id})).mappings().first()
        if not parcel:
            return None

        latest_soil_q = text("""
            SELECT r.measured_at, r.soil_temperature_c, r.soil_moisture_pct,
                   r.battery_v, r.transport, s.device_uid
            FROM soil_readings r
            JOIN stakes s ON s.id = r.stake_id
            WHERE s.parcel_id = :parcel_id AND s.is_active AND NOT r.is_simulated
            ORDER BY r.measured_at DESC
            LIMIT 1
        """)
        latest_soil = (
            await self.db.execute(latest_soil_q, {"parcel_id": parcel_id})
        ).mappings().first()

        ph_q = text("""
            SELECT observation_id, ph, method, observed_at
            FROM latest_soil_ph
            WHERE parcel_id = :parcel_id
        """)
        latest_ph = (await self.db.execute(ph_q, {"parcel_id": parcel_id})).mappings().first()

        rain_data = None
        if parcel["latest_weather_dt"]:
            rain_q = text("""
                SELECT precip_total_mm, origin, precip_product, days_with_data, window_days, last_valid_date
                FROM rainfall_window(:parcel_id, :end_dt, 30, 0.8)
            """)
            rain_row = (
                await self.db.execute(
                    rain_q, {"parcel_id": parcel_id, "end_dt": parcel["latest_weather_dt"]}
                )
            ).mappings().first()
            rain_data = dict(rain_row) if rain_row else None

        return {
            "parcel_id": parcel["id"],
            "parcel_name": parcel["name"],
            "latest_soil_reading": dict(latest_soil) if latest_soil else None,
            "latest_ph": {
                **dict(latest_ph),
                "is_simulated": latest_ph["method"] == "simulado",
            }
            if latest_ph
            else None,
            "rainfall_30d": rain_data,
        }

    async def get_soil_history(
        self, parcel_id: UUID, since: datetime, limit: int = 500
    ) -> list[dict[str, Any]]:
        q = text("""
            SELECT r.measured_at, r.soil_temperature_c, r.soil_moisture_pct,
                   r.battery_v, r.transport, s.device_uid
            FROM soil_readings r
            JOIN stakes s ON s.id = r.stake_id
            WHERE s.parcel_id = :parcel_id
              AND r.measured_at >= :since
              AND NOT r.is_simulated
            ORDER BY r.measured_at ASC
            LIMIT :limit
        """)
        return [
            dict(r)
            for r in (
                await self.db.execute(q, {"parcel_id": parcel_id, "since": since, "limit": limit})
            ).mappings().all()
        ]

    async def get_ph_history(self, parcel_id: UUID, limit: int = 100) -> list[dict[str, Any]]:
        q = text("""
            SELECT id, observed_at, ph, method, (method = 'simulado') AS is_simulated, notes
            FROM soil_ph_observations
            WHERE parcel_id = :parcel_id
            ORDER BY observed_at DESC
            LIMIT :limit
        """)
        return [
            dict(r)
            for r in (await self.db.execute(q, {"parcel_id": parcel_id, "limit": limit})).mappings().all()
        ]

    async def get_rainfall_history(self, parcel_id: UUID, days: int = 30) -> list[dict[str, Any]]:
        q = text("""
            SELECT w.obs_date, w.precip_mm, 'nasa_power' AS origin, w.precip_product,
                   w.air_temp_c, w.rel_humidity
            FROM parcels p
            JOIN weather_daily w ON w.cell_id = p.climate_cell_id
            WHERE p.id = :parcel_id
              AND w.obs_date >= CURRENT_DATE - make_interval(days => :days)
            ORDER BY w.obs_date ASC
        """)
        return [
            dict(r)
            for r in (await self.db.execute(q, {"parcel_id": parcel_id, "days": days})).mappings().all()
        ]