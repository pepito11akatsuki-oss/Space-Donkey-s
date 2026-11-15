from typing import Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class CropRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_crops(self, soil_texture: str | None = None) -> list[dict[str, Any]]:
        q = text("""
            SELECT c.id, c.common_name_es, c.scientific_name, c.dataset_label,
                   c.category, c.cycle_days_min, c.cycle_days_max, c.harvest_notes,
                   ds.name AS source_name, ds.citation AS source_citation
            FROM crops c
            LEFT JOIN data_sources ds ON ds.id = c.source_id
            ORDER BY c.common_name_es
        """)
        crops = [dict(r) for r in (await self.db.execute(q)).mappings().all()]

        req_q = text("""
            SELECT cr.crop_id, cr.variable, cr.abs_min, cr.optimal_min,
                   cr.optimal_max, cr.abs_max, cr.unit, cr.method,
                   ds.name AS source_name
            FROM crop_requirements cr
            JOIN data_sources ds ON ds.id = cr.source_id
        """)
        reqs = (await self.db.execute(req_q)).mappings().all()

        moisture_map: dict[int, dict[str, Any]] = {}
        if soil_texture:
            m_q = text("""
                SELECT crop_id, optimal_min_pct, optimal_max_pct
                FROM v_crop_moisture_range
                WHERE texture_code = :texture
            """)
            for mr in (await self.db.execute(m_q, {"texture": soil_texture})).mappings().all():
                moisture_map[mr["crop_id"]] = {
                    "optimal_min": float(mr["optimal_min_pct"]),
                    "optimal_max": float(mr["optimal_max_pct"]),
                    "unit": "% vol",
                    "source_name": "FAO-56",
                }

        by_id = {c["id"]: {**c, "requirements": {}} for c in crops}
        for r in reqs:
            if r["crop_id"] in by_id:
                by_id[r["crop_id"]]["requirements"][r["variable"]] = {
                    "optimal_min": float(r["optimal_min"]),
                    "optimal_max": float(r["optimal_max"]),
                    "unit": r["unit"],
                    "source_name": r["source_name"],
                }
        for cid, m_data in moisture_map.items():
            if cid in by_id:
                by_id[cid]["requirements"]["soil_moisture"] = m_data

        return list(by_id.values())

    async def list_textures(self) -> list[dict[str, Any]]:
        q = text("SELECT code, name_es FROM soil_texture_classes ORDER BY name_es")
        return [dict(r) for r in (await self.db.execute(q)).mappings().all()]