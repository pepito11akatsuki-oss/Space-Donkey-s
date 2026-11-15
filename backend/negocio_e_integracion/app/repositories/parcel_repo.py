from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class ParcelRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def resolve_climate_cell(self, lat: Decimal, lon: Decimal) -> UUID:
        q = text("""
            WITH center AS (
                SELECT center_lat, center_lon FROM nasa_grid_center(:lat, :lon)
            )
            INSERT INTO climate_cells (source, center_lat, center_lon)
            SELECT 'nasa_power', center_lat, center_lon FROM center
            ON CONFLICT (source, center_lat, center_lon)
            DO UPDATE SET center_lat = EXCLUDED.center_lat
            RETURNING id
        """)
        return (await self.db.execute(q, {"lat": lat, "lon": lon})).scalar_one()

    async def create(
        self,
        org_id: UUID,
        name: str,
        latitude: Decimal | None,
        longitude: Decimal | None,
        area_ha: Decimal | None,
        soil_texture: str | None,
        climate_cell_id: UUID | None,
    ) -> dict[str, Any]:
        q = text("""
            INSERT INTO parcels (org_id, name, latitude, longitude, area_ha, climate_cell_id, soil_texture)
            VALUES (:org_id, :name, :lat, :lon, :area_ha, :cell_id, :texture)
            RETURNING id, org_id, name, latitude, longitude, area_ha, climate_cell_id, soil_texture, created_at
        """)
        row = (
            await self.db.execute(
                q,
                {
                    "org_id": org_id,
                    "name": name,
                    "lat": latitude,
                    "lon": longitude,
                    "area_ha": area_ha,
                    "cell_id": climate_cell_id,
                    "texture": soil_texture,
                },
            )
        ).mappings().one()
        return dict(row)

    async def list_all(self) -> list[dict[str, Any]]:
        q = text("""
            SELECT p.id, p.name, p.latitude, p.longitude, p.area_ha,
                   p.soil_texture, st.name_es AS soil_texture_name, p.created_at,
                   (SELECT count(*)::int FROM stakes s WHERE s.parcel_id = p.id AND s.is_active) AS active_stakes,
                   (SELECT count(*)::int FROM alerts a
                    LEFT JOIN stakes s ON s.id = a.stake_id
                    WHERE a.resolved_at IS NULL AND (a.parcel_id = p.id OR s.parcel_id = p.id)) AS open_alerts
            FROM parcels p
            LEFT JOIN soil_texture_classes st ON st.code = p.soil_texture
            ORDER BY p.created_at DESC
        """)
        return [dict(r) for r in (await self.db.execute(q)).mappings().all()]

    async def get_by_id(self, parcel_id: UUID) -> dict[str, Any] | None:
        q = text("""
            SELECT p.id, p.name, p.latitude, p.longitude, p.area_ha,
                   p.climate_cell_id, p.soil_texture, st.name_es AS soil_texture_name, p.created_at
            FROM parcels p
            LEFT JOIN soil_texture_classes st ON st.code = p.soil_texture
            WHERE p.id = :parcel_id
        """)
        row = (await self.db.execute(q, {"parcel_id": parcel_id})).mappings().first()
        return dict(row) if row else None

    async def update(self, parcel_id: UUID, fields: dict[str, Any]) -> dict[str, Any] | None:
        if not fields:
            return await self.get_by_id(parcel_id)
        set_clauses = ", ".join(f"{k} = :{k}" for k in fields)
        q = text(f"""
            UPDATE parcels SET {set_clauses}
            WHERE id = :parcel_id
            RETURNING id, org_id, name, latitude, longitude, area_ha, climate_cell_id, soil_texture, created_at
        """)
        row = (await self.db.execute(q, {**fields, "parcel_id": parcel_id})).mappings().first()
        return dict(row) if row else None

    async def assign_crop(
        self, parcel_id: UUID, crop_id: int, status: str, sown_at: date | None
    ) -> dict[str, Any]:
        q = text("""
            INSERT INTO parcel_crops (parcel_id, crop_id, status, sown_at)
            VALUES (:parcel_id, :crop_id, :status, :sown_at)
            ON CONFLICT (parcel_id, crop_id, status)
            DO UPDATE SET sown_at = COALESCE(EXCLUDED.sown_at, parcel_crops.sown_at)
            RETURNING id, parcel_id, crop_id, status, sown_at, created_at
        """)
        row = (
            await self.db.execute(
                q,
                {"parcel_id": parcel_id, "crop_id": crop_id, "status": status, "sown_at": sown_at},
            )
        ).mappings().one()
        return dict(row)

    async def list_crops(self, parcel_id: UUID) -> list[dict[str, Any]]:
        q = text("""
            SELECT pc.id, pc.crop_id, c.common_name_es, c.scientific_name,
                   pc.status, pc.sown_at, pc.created_at
            FROM parcel_crops pc
            JOIN crops c ON c.id = pc.crop_id
            WHERE pc.parcel_id = :parcel_id
            ORDER BY pc.created_at DESC
        """)
        return [dict(r) for r in (await self.db.execute(q, {"parcel_id": parcel_id})).mappings().all()]