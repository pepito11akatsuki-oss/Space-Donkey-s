from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentPrincipal, get_tenant_db, require_roles

router = APIRouter(tags=["Motor de Recomendaciones"])

ALLOWED_CHECK_ORIGINS = {
    "estaca",
    "nasa_power",
    "simulado",
    "manual",
    "laboratorio",
    "dataset_estimado",
}

PH_METHOD_TO_ORIGIN = {
    "simulado": "simulado",
    "kit_manual": "manual",
    "laboratorio": "laboratorio",
    "dataset_estimado": "dataset_estimado",
}


class EvaluateRecommendationRequest(BaseModel):
    soil_window_days: int = Field(default=7, ge=1, le=90)
    rainfall_window_days: int = Field(default=30, ge=1, le=365)
    include_simulated: bool = False
    crop_ids: list[int] | None = None


class AttachMlScoreRequest(BaseModel):
    ml_suitability_score: Decimal = Field(ge=0, le=100)
    projected_days: int | None = Field(default=None, gt=0)
    future_risk_summary: str | None = Field(default=None, max_length=1000)


def _round2(val: Decimal | float | None) -> Decimal | None:
    if val is None:
        return None
    return Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@router.post(
    "/parcels/{parcel_id}/recommendations/evaluate",
    status_code=status.HTTP_201_CREATED,
)
async def evaluate_parcel_recommendations(
    parcel_id: UUID,
    body: EvaluateRecommendationRequest,
    principal: CurrentPrincipal = Depends(require_roles("owner", "agronomist")),
    db: AsyncSession = Depends(get_tenant_db),
):
    parcel = (
        await db.execute(
            text("""
                SELECT id, climate_cell_id,
                       COALESCE(latest_weather_date(climate_cell_id), CURRENT_DATE) AS window_end
                FROM parcels
                WHERE id = :pid
            """),
            {"pid": parcel_id},
        )
    ).first()
    if not parcel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parcela no encontrada en tu organización",
        )

    window_end: date = parcel.window_end

    soil = (
        await db.execute(
            text("SELECT * FROM soil_window(:pid, :wend, :sdays, :inc_sim)"),
            {
                "pid": parcel_id,
                "wend": window_end,
                "sdays": body.soil_window_days,
                "inc_sim": body.include_simulated,
            },
        )
    ).first()

    rain = (
        await db.execute(
            text("SELECT * FROM rainfall_window(:pid, :wend, :rdays, 0.8)"),
            {
                "pid": parcel_id,
                "wend": window_end,
                "rdays": body.rainfall_window_days,
            },
        )
    ).first()

    ph_row = (
        await db.execute(
            text("""
                SELECT id, ph, method::text AS method
                FROM soil_ph_observations
                WHERE parcel_id = :pid
                ORDER BY observed_at DESC
                LIMIT 1
            """),
            {"pid": parcel_id},
        )
    ).first()

    if body.crop_ids:
        crops = (
            await db.execute(
                text("SELECT id, common_name_es FROM crops WHERE id = ANY(:cids) ORDER BY id"),
                {"cids": body.crop_ids},
            )
        ).all()
    else:
        crops = (
            await db.execute(text("SELECT id, common_name_es FROM crops ORDER BY id"))
        ).all()

    if not crops:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No hay cultivos disponibles en el catálogo para evaluar",
        )

    run = (
        await db.execute(
            text("""
                INSERT INTO recommendation_runs (
                    parcel_id, soil_window_days, rainfall_window_days, window_end, created_by
                )
                VALUES (:pid, :sdays, :rdays, :wend, :uid)
                RETURNING id, parcel_id, soil_window_days, rainfall_window_days, window_end, created_at
            """),
            {
                "pid": parcel_id,
                "sdays": body.soil_window_days,
                "rdays": body.rainfall_window_days,
                "wend": window_end,
                "uid": principal.user_id,
            },
        )
    ).one()

    soil_origin = "simulado" if body.include_simulated else "estaca"
    raw_rain_origin = getattr(rain, "origin", None) if rain else None
    rain_origin = (
        raw_rain_origin
        if raw_rain_origin in ALLOWED_CHECK_ORIGINS
        else ("nasa_power" if rain and rain.precip_total_mm is not None else None)
    )
    ph_origin = PH_METHOD_TO_ORIGIN.get(ph_row.method, "manual") if ph_row else None

    observations: dict[str, dict] = {
        "soil_temperature": {
            "measured": _round2(soil.soil_temp_avg) if soil else None,
            "origin": soil_origin if (soil and soil.soil_temp_avg is not None) else None,
            "is_simulated": body.include_simulated,
            "ph_observation_id": None,
        },
        "soil_moisture": {
            "measured": _round2(soil.soil_moisture_avg) if soil else None,
            "origin": soil_origin if (soil and soil.soil_moisture_avg is not None) else None,
            "is_simulated": body.include_simulated,
            "ph_observation_id": None,
        },
        "soil_ph": {
            "measured": _round2(ph_row.ph) if ph_row else None,
            "origin": ph_origin,
            "is_simulated": (ph_row.method == "simulado") if ph_row else False,
            "ph_observation_id": ph_row.id if ph_row else None,
        },
        "rainfall": {
            "measured": _round2(rain.precip_total_mm) if rain else None,
            "origin": rain_origin,
            "is_simulated": False,
            "ph_observation_id": None,
        },
    }

    advice_rows = (
        await db.execute(
            text("SELECT id, variable::text AS variable, status::text AS status FROM advice_rules")
        )
    ).all()
    advice_map = {(r.variable, r.status): r.id for r in advice_rows}

    req_rows = (
        await db.execute(
            text("""
                SELECT crop_id, variable::text AS variable, optimal_min, optimal_max
                FROM crop_requirements
            """)
        )
    ).all()
    req_map = {(r.crop_id, r.variable): (r.optimal_min, r.optimal_max) for r in req_rows}

    evaluated_crops = []
    for crop in crops:
        checks_to_insert = []
        variables_ok = 0

        for var_name in ("soil_temperature", "soil_moisture", "soil_ph", "rainfall"):
            obs = observations[var_name]
            measured = obs["measured"]
            bounds = req_map.get((crop.id, var_name))

            if measured is None or bounds is None:
                check_status = "not_evaluated"
                measured_db = None
                advice_id = None
            else:
                opt_min, opt_max = bounds
                measured_db = measured
                if measured < opt_min:
                    check_status = "below"
                elif measured > opt_max:
                    check_status = "above"
                else:
                    check_status = "in_range"
                    variables_ok += 1
                advice_id = advice_map.get((var_name, check_status))

            checks_to_insert.append(
                {
                    "run_id": run.id,
                    "crop_id": crop.id,
                    "variable": var_name,
                    "measured": measured_db,
                    "status": check_status,
                    "origin": obs["origin"],
                    "is_simulated": obs["is_simulated"],
                    "ph_observation_id": obs["ph_observation_id"],
                    "advice_id": advice_id,
                }
            )

        if variables_ok == 4:
            classification = "recomendado"
        elif variables_ok == 3:
            classification = "condicionado"
        else:
            classification = "no_recomendado"

        await db.execute(
            text("""
                INSERT INTO recommendation_results (run_id, crop_id, variables_ok, classification)
                VALUES (:run_id, :crop_id, :vars_ok, CAST(:cls AS viability_class))
            """),
            {
                "run_id": run.id,
                "crop_id": crop.id,
                "vars_ok": variables_ok,
                "cls": classification,
            },
        )

        for chk in checks_to_insert:
            await db.execute(
                text("""
                    INSERT INTO recommendation_checks (
                        run_id, crop_id, variable, measured, status,
                        origin, is_simulated, ph_observation_id, advice_id
                    )
                    VALUES (
                        :run_id, :crop_id, CAST(:variable AS variable_code),
                        :measured, CAST(:status AS check_status),
                        :origin, :is_simulated, :ph_observation_id, :advice_id
                    )
                """),
                chk,
            )

        evaluated_crops.append(
            {
                "crop_id": crop.id,
                "common_name_es": crop.common_name_es,
                "variables_ok": variables_ok,
                "classification": classification,
            }
        )

    evaluated_crops.sort(key=lambda c: c["variables_ok"], reverse=True)
    return {
        "run": dict(run._mapping),
        "results": evaluated_crops,
    }


@router.get("/parcels/{parcel_id}/recommendations")
async def list_parcel_recommendation_runs(
    parcel_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_tenant_db),
):
    rows = (
        await db.execute(
            text("""
                SELECT id, parcel_id, soil_window_days, rainfall_window_days,
                       window_end, created_by, created_at
                FROM recommendation_runs
                WHERE parcel_id = :pid
                ORDER BY created_at DESC
                LIMIT :lim
            """),
            {"pid": parcel_id, "lim": limit},
        )
    ).all()
    return [dict(r._mapping) for r in rows]


@router.get("/recommendations/{run_id}")
async def get_recommendation_run_detail(
    run_id: UUID,
    db: AsyncSession = Depends(get_tenant_db),
):
    run = (
        await db.execute(
            text("""
                SELECT id, parcel_id, soil_window_days, rainfall_window_days,
                       window_end, created_by, created_at
                FROM recommendation_runs
                WHERE id = :rid
            """),
            {"rid": run_id},
        )
    ).first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ejecución de recomendación no encontrada",
        )

    results = (
        await db.execute(
            text("""
                SELECT rr.crop_id, c.common_name_es, c.scientific_name,
                       rr.variables_ok, rr.classification::text AS classification,
                       rr.ml_suitability_score, rr.projected_days, rr.future_risk_summary
                FROM recommendation_results rr
                JOIN crops c ON c.id = rr.crop_id
                WHERE rr.run_id = :rid
                ORDER BY rr.variables_ok DESC, rr.ml_suitability_score DESC NULLS LAST
            """),
            {"rid": run_id},
        )
    ).all()

    checks = (
        await db.execute(
            text("""
                SELECT rc.crop_id, rc.variable::text AS variable, rc.measured,
                       rc.status::text AS status, rc.origin, rc.is_simulated,
                       rc.ph_observation_id, ar.message_es AS advice_message
                FROM recommendation_checks rc
                LEFT JOIN advice_rules ar ON ar.id = rc.advice_id
                WHERE rc.run_id = :rid
                ORDER BY rc.crop_id, rc.variable
            """),
            {"rid": run_id},
        )
    ).all()

    checks_by_crop: dict[int, list[dict]] = {}
    for chk in checks:
        checks_by_crop.setdefault(chk.crop_id, []).append(dict(chk._mapping))

    enriched_results = [
        {
            **dict(res._mapping),
            "checks": checks_by_crop.get(res.crop_id, []),
        }
        for res in results
    ]

    return {
        "run": dict(run._mapping),
        "results": enriched_results,
    }


@router.patch("/recommendations/{run_id}/crops/{crop_id}/ml")
async def attach_ml_suitability_score(
    run_id: UUID,
    crop_id: int,
    body: AttachMlScoreRequest,
    principal: CurrentPrincipal = Depends(require_roles("owner", "agronomist")),
    db: AsyncSession = Depends(get_tenant_db),
):
    row = (
        await db.execute(
            text("""
                UPDATE recommendation_results
                SET ml_suitability_score = :score,
                    projected_days = COALESCE(:pdays, projected_days),
                    future_risk_summary = COALESCE(:risk, future_risk_summary)
                WHERE run_id = :rid AND crop_id = :cid
                RETURNING run_id, crop_id, variables_ok, classification::text AS classification,
                          ml_suitability_score, projected_days, future_risk_summary
            """),
            {
                "rid": run_id,
                "cid": crop_id,
                "score": body.ml_suitability_score,
                "pdays": body.projected_days,
                "risk": body.future_risk_summary,
            },
        )
    ).first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resultado de cultivo no encontrado en esa ejecución",
        )
    return dict(row._mapping)
