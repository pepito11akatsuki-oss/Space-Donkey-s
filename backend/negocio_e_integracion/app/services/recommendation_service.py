from datetime import date, datetime, timezone
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import DomainValidationError, NotFoundError
from app.integrations.ai_engine_client import AIEngineClient
from app.repositories.recommendation_repo import RecommendationRepository
from app.schemas.recommendations import RecommendationRunRequest


class RecommendationService:
    def __init__(self, db: AsyncSession, ai_client: AIEngineClient | None = None):
        self.repo = RecommendationRepository(db)
        self.ai_client = ai_client or AIEngineClient()

    async def evaluate_and_persist(self, req: RecommendationRunRequest, user_id: UUID) -> dict:
        parcel = await self.repo.get_parcel_context(req.parcel_id)
        if not parcel:
            raise NotFoundError("La parcela no existe o no pertenece a tu organización.")

        window_end: date = parcel["latest_weather_dt"] or datetime.now(timezone.utc).date()
        agg = await self.repo.get_window_aggregates(
            parcel_id=req.parcel_id,
            window_end=window_end,
            soil_days=req.soil_window_days,
            rain_days=req.rainfall_window_days,
            include_simulated=req.include_simulated_soil,
        )

        crops_bundle = await self.repo.get_crop_requirements_bundle(
            soil_texture=parcel["soil_texture"],
            crop_ids=req.crop_ids,
        )
        if not crops_bundle:
            raise DomainValidationError("No hay cultivos disponibles para evaluar.")

        ph_data = agg["ph"]
        ph_method = ph_data["method"] if ph_data else None
        ph_obs_id = ph_data["observation_id"] if ph_data else None
        ph_is_sim = (ph_method == "simulado") if ph_method else False

        ai_payload = {
            "parcel_id": str(req.parcel_id),
            "soil_texture": parcel["soil_texture"],
            "windows": {
                "soil_window_days": req.soil_window_days,
                "rainfall_window_days": req.rainfall_window_days,
                "window_end": window_end.isoformat(),
            },
            "observed_variables": {
                "soil_temperature": {
                    "value": float(agg["soil"]["soil_temp_avg"])
                    if agg["soil"]["soil_temp_avg"] is not None
                    else None,
                    "unit": "°C",
                    "origin": "estaca",
                    "is_simulated": req.include_simulated_soil,
                },
                "soil_moisture": {
                    "value": float(agg["soil"]["soil_moisture_avg"])
                    if agg["soil"]["soil_moisture_avg"] is not None
                    else None,
                    "unit": "% vol",
                    "origin": "estaca",
                    "is_simulated": req.include_simulated_soil,
                },
                "soil_ph": {
                    "value": float(ph_data["ph"]) if ph_data else None,
                    "unit": "pH",
                    "origin": ph_method if ph_method else "simulado",
                    "ph_method": ph_method,
                    "is_simulated": ph_is_sim,
                },
                "rainfall": {
                    "value": float(agg["rainfall"]["precip_total_mm"])
                    if agg["rainfall"]["precip_total_mm"] is not None
                    else None,
                    "unit": "mm",
                    "origin": "nasa_power",
                    "is_simulated": False,
                },
            },
            "candidate_crops": crops_bundle,
        }

        ai_result = await self.ai_client.evaluate_parcel(ai_payload)

        run_row = await self.repo.insert_run(
            parcel_id=req.parcel_id,
            soil_window_days=req.soil_window_days,
            rainfall_window_days=req.rainfall_window_days,
            window_end=window_end,
            created_by=user_id,
        )
        run_id: UUID = run_row["id"]
        crop_lookup = {c["crop_id"]: c for c in crops_bundle}
        results_out = []

        for ev in ai_result.evaluations:
            crop_meta = crop_lookup.get(ev.crop_id)
            if not crop_meta:
                continue

            await self.repo.insert_result(
                run_id=run_id,
                crop_id=ev.crop_id,
                variables_ok=ev.variables_ok,
                classification=ev.classification,
                ml_suitability_score=ev.ml_suitability_score,
                projected_days=ev.projected_days,
                future_risk_summary=ev.future_risk_summary,
            )

            checks_out = []
            for chk in ev.checks:
                advice_rule = await self.repo.get_advice_rule(chk.variable, chk.status)
                advice_id = advice_rule["id"] if advice_rule else None
                advice_text = None

                if advice_rule and chk.measured is not None:
                    req_range = crop_meta["requirements"].get(chk.variable, {})
                    fallback_target = (
                        req_range.get("optimal_min")
                        if chk.status == "below"
                        else req_range.get("optimal_max")
                    )
                    target_val = chk.target_value if chk.target_value is not None else fallback_target
                    advice_text = advice_rule["message_es"].format(
                        current=chk.measured,
                        target=target_val if target_val is not None else "rango óptimo",
                    )

                is_sim = True if (chk.variable == "soil_ph" and ph_is_sim) else chk.is_simulated
                origin = None if chk.status == "not_evaluated" else (
                    "simulado" if (chk.variable == "soil_ph" and ph_is_sim) else chk.origin
                )

                await self.repo.insert_check(
                    run_id=run_id,
                    crop_id=ev.crop_id,
                    variable=chk.variable,
                    measured=chk.measured,
                    status=chk.status,
                    origin=origin,
                    is_simulated=is_sim,
                    ph_observation_id=ph_obs_id if chk.variable == "soil_ph" else None,
                    advice_id=advice_id,
                )

                checks_out.append(
                    {
                        "variable": chk.variable,
                        "measured": float(chk.measured) if chk.measured is not None else None,
                        "status": chk.status,
                        "origin": origin,
                        "is_simulated": is_sim,
                        "ph_method": ph_method if chk.variable == "soil_ph" else None,
                        "advice_text": advice_text,
                    }
                )

            results_out.append(
                {
                    "crop_id": ev.crop_id,
                    "common_name_es": crop_meta["common_name_es"],
                    "scientific_name": crop_meta["scientific_name"],
                    "variables_ok": ev.variables_ok,
                    "classification": ev.classification,
                    "ml_suitability_score": float(ev.ml_suitability_score)
                    if ev.ml_suitability_score is not None
                    else None,
                    "projected_days": ev.projected_days,
                    "future_risk_summary": ev.future_risk_summary,
                    "checks": checks_out,
                }
            )

        return {
            "run_id": str(run_id),
            "parcel_id": str(req.parcel_id),
            "soil_window_days": req.soil_window_days,
            "rainfall_window_days": req.rainfall_window_days,
            "window_end": window_end.isoformat(),
            "created_at": run_row["created_at"].isoformat(),
            "results": results_out,
        }