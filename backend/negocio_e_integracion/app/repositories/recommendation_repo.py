from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class RecommendationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_parcel_context(self, parcel_id: UUID) -> dict[str, Any] | None:
        q = text("""
            SELECT p.id, p.name, p.soil_texture, p.climate_cell_id,
                   latest_weather_date(p.climate_cell_id) AS latest_weather_dt
            FROM parcels p
            WHERE p.id = :parcel_id
        """)
        row = (await self.db.execute(q, {"parcel_id": parcel_id})).mappings().first()
        return dict(row) if row else None

    async def get_window_aggregates(
        self,
        parcel_id: UUID,
        window_end: date,
        soil_days: int,
        rain_days: int,
        include_simulated: bool,
    ) -> dict[str, Any]:
        soil_q = text("""
            SELECT soil_temp_avg, soil_moisture_avg, readings_count
            FROM soil_window(:parcel_id, :window_end, :soil_days, :include_sim)
        """)
        rain_q = text("""
            SELECT precip_total_mm, origin, precip_product, days_with_data, window_days, last_valid_date
            FROM rainfall_window(:parcel_id, :window_end, :rain_days, 0.8)
        """)
        ph_q = text("""
            SELECT observation_id, ph, method, observed_at
            FROM latest_soil_ph
            WHERE parcel_id = :parcel_id
        """)

        soil_row = (
            await self.db.execute(
                soil_q,
                {
                    "parcel_id": parcel_id,
                    "window_end": window_end,
                    "soil_days": soil_days,
                    "include_sim": include_simulated,
                },
            )
        ).mappings().one()

        rain_row = (
            await self.db.execute(
                rain_q,
                {"parcel_id": parcel_id, "window_end": window_end, "rain_days": rain_days},
            )
        ).mappings().one()

        ph_row = (await self.db.execute(ph_q, {"parcel_id": parcel_id})).mappings().first()

        return {
            "soil": dict(soil_row),
            "rainfall": dict(rain_row),
            "ph": dict(ph_row) if ph_row else None,
        }

    async def get_crop_requirements_bundle(
        self, soil_texture: str | None, crop_ids: list[int] | None
    ) -> list[dict[str, Any]]:
        filter_clause = "WHERE c.id = ANY(:crop_ids)" if crop_ids else ""
        q = text(f"""
            SELECT c.id AS crop_id, c.common_name_es, c.scientific_name,
                   c.cycle_days_min, c.cycle_days_max,
                   cr.variable, cr.optimal_min, cr.optimal_max, cr.unit
            FROM crops c
            LEFT JOIN crop_requirements cr ON cr.crop_id = c.id
            {filter_clause}
            ORDER BY c.id
        """)
        params: dict[str, Any] = {"crop_ids": crop_ids} if crop_ids else {}
        rows = (await self.db.execute(q, params)).mappings().all()

        moisture_map: dict[int, tuple[Decimal, Decimal]] = {}
        if soil_texture:
            m_q = text("""
                SELECT crop_id, optimal_min_pct, optimal_max_pct
                FROM v_crop_moisture_range
                WHERE texture_code = :texture
            """)
            for mr in (await self.db.execute(m_q, {"texture": soil_texture})).mappings().all():
                moisture_map[mr["crop_id"]] = (mr["optimal_min_pct"], mr["optimal_max_pct"])

        crops_dict: dict[int, dict[str, Any]] = {}
        for r in rows:
            cid = r["crop_id"]
            if cid not in crops_dict:
                crops_dict[cid] = {
                    "crop_id": cid,
                    "common_name_es": r["common_name_es"],
                    "scientific_name": r["scientific_name"],
                    "cycle_days_min": r["cycle_days_min"],
                    "cycle_days_max": r["cycle_days_max"],
                    "requirements": {},
                }
                if cid in moisture_map:
                    m_min, m_max = moisture_map[cid]
                    crops_dict[cid]["requirements"]["soil_moisture"] = {
                        "optimal_min": float(m_min),
                        "optimal_max": float(m_max),
                        "unit": "% vol",
                    }
            if r["variable"]:
                crops_dict[cid]["requirements"][r["variable"]] = {
                    "optimal_min": float(r["optimal_min"]),
                    "optimal_max": float(r["optimal_max"]),
                    "unit": r["unit"],
                }

        return list(crops_dict.values())

    async def get_advice_rule(self, variable: str, status: str) -> dict[str, Any] | None:
        if status not in ("below", "above"):
            return None
        q = text("SELECT id, message_es FROM advice_rules WHERE variable = :variable AND status = :status")
        row = (await self.db.execute(q, {"variable": variable, "status": status})).mappings().first()
        return dict(row) if row else None

    async def insert_run(
        self,
        parcel_id: UUID,
        soil_window_days: int,
        rainfall_window_days: int,
        window_end: date,
        created_by: UUID,
    ) -> dict[str, Any]:
        q = text("""
            INSERT INTO recommendation_runs (
                parcel_id, soil_window_days, rainfall_window_days, window_end, created_by
            )
            VALUES (:parcel_id, :soil_days, :rain_days, :window_end, :created_by)
            RETURNING id, created_at
        """)
        row = (
            await self.db.execute(
                q,
                {
                    "parcel_id": parcel_id,
                    "soil_days": soil_window_days,
                    "rain_days": rainfall_window_days,
                    "window_end": window_end,
                    "created_by": created_by,
                },
            )
        ).mappings().one()
        return dict(row)

    async def insert_result(
        self,
        run_id: UUID,
        crop_id: int,
        variables_ok: int,
        classification: str,
        ml_suitability_score: Decimal | None,
        projected_days: int | None,
        future_risk_summary: str | None,
    ) -> None:
        q = text("""
            INSERT INTO recommendation_results (
                run_id, crop_id, variables_ok, classification,
                ml_suitability_score, projected_days, future_risk_summary
            )
            VALUES (
                :run_id, :crop_id, :variables_ok, :classification,
                :ml_score, :proj_days, :risk_summary
            )
        """)
        await self.db.execute(
            q,
            {
                "run_id": run_id,
                "crop_id": crop_id,
                "variables_ok": variables_ok,
                "classification": classification,
                "ml_score": ml_suitability_score,
                "proj_days": projected_days,
                "risk_summary": future_risk_summary,
            },
        )

    async def insert_check(
        self,
        run_id: UUID,
        crop_id: int,
        variable: str,
        measured: Decimal | None,
        status: str,
        origin: str | None,
        is_simulated: bool,
        ph_observation_id: UUID | None,
        advice_id: int | None,
    ) -> None:
        q = text("""
            INSERT INTO recommendation_checks (
                run_id, crop_id, variable, measured, status,
                origin, is_simulated, ph_observation_id, advice_id
            )
            VALUES (
                :run_id, :crop_id, :variable, :measured, :status,
                :origin, :is_simulated, :ph_observation_id, :advice_id
            )
        """)
        await self.db.execute(
            q,
            {
                "run_id": run_id,
                "crop_id": crop_id,
                "variable": variable,
                "measured": measured,
                "status": status,
                "origin": origin,
                "is_simulated": is_simulated,
                "ph_observation_id": ph_observation_id,
                "advice_id": advice_id,
            },
        )

    @staticmethod
    def evaluate_history_safety(
        checks: list[dict[str, Any]],
    ) -> tuple[str, bool]:
        expected = {
            "soil_temperature",
            "soil_moisture",
            "soil_ph",
            "rainfall",
        }

        if len(checks) != 4:
            return "incomplete", False

        variables = [check.get("variable") for check in checks]

        if set(variables) != expected:
            return "incomplete", False

        for check in checks:
            if check.get("measured") is None:
                return "incomplete", False

            if check.get("status") not in {
                "in_range",
                "below",
                "above",
            }:
                return "incomplete", False

            if check.get("is_simulated") is not False:
                return "incomplete", False

            origin = check.get("origin")

            if origin in {
                None,
                "simulado",
                "dataset_estimado",
            }:
                return "incomplete", False

            if (
                check["variable"] == "rainfall"
                and origin != "nasa_power"
            ):
                return "incomplete", False

        return "complete", True

    async def list_parcel_runs(self, parcel_id: UUID, limit: int = 10) -> list[dict[str, Any]]:
        runs_q = text("""
            SELECT id, soil_window_days, rainfall_window_days, window_end, created_at
            FROM recommendation_runs
            WHERE parcel_id = :parcel_id
            ORDER BY created_at DESC
            LIMIT :limit
        """)
        runs = [
            dict(r)
            for r in (await self.db.execute(runs_q, {"parcel_id": parcel_id, "limit": limit})).mappings().all()
        ]
        if not runs:
            return []

        run_ids = [r["id"] for r in runs]
        res_q = text("""
            SELECT rr.run_id, rr.crop_id, c.common_name_es, c.scientific_name,
                   rr.variables_ok, rr.classification,
                   rr.ml_suitability_score, rr.projected_days, rr.future_risk_summary
            FROM recommendation_results rr
            JOIN crops c ON c.id = rr.crop_id
            WHERE rr.run_id = ANY(:run_ids)
            ORDER BY rr.variables_ok DESC, rr.ml_suitability_score DESC NULLS LAST
        """)
        results = (await self.db.execute(res_q, {"run_ids": run_ids})).mappings().all()

        chk_q = text("""
            SELECT rc.run_id, rc.crop_id, rc.variable, rc.measured, rc.status,
                   rc.origin, rc.is_simulated, ar.message_es AS advice_template
            FROM recommendation_checks rc
            LEFT JOIN advice_rules ar ON ar.id = rc.advice_id
            WHERE rc.run_id = ANY(:run_ids)
        """)
        checks = (await self.db.execute(chk_q, {"run_ids": run_ids})).mappings().all()

        checks_by_key: dict[tuple[UUID, int], list[dict[str, Any]]] = {}
        for c in checks:
            checks_by_key.setdefault((c["run_id"], c["crop_id"]), []).append(dict(c))

        res_by_run: dict[UUID, list[dict[str, Any]]] = {}
        for res in results:
            item = dict(res)
            item["checks"] = checks_by_key.get((res["run_id"], res["crop_id"]), [])
            status, eligible = self.evaluate_history_safety(item["checks"])
            item["evaluation_status"] = status
            item["recommendation_eligible"] = eligible

            if not eligible:
                for check in item["checks"]:
                    check["advice_template"] = None

            res_by_run.setdefault(res["run_id"], []).append(item)

        for r in runs:
            r["results"] = res_by_run.get(r["id"], [])
        return runs