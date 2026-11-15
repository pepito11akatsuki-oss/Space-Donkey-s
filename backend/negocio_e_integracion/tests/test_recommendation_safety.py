from app.schemas.recommendations import AICropEvaluationOutput


def test_incomplete_evaluation_preserves_safety_flags():
    data = {
        "crop_id": 1,
        "variables_ok": 4,
        "classification": "recomendado",
        "evaluation_status": "incomplete",
        "recommendation_eligible": False,
        "checks": [
            {
                "variable": variable,
                "measured": value,
                "status": "in_range",
                "origin": origin,
                "is_simulated": simulated,
                "target_value": None,
            }
            for variable, value, origin, simulated in [
                ("soil_temperature", 23.5, "estaca", False),
                ("soil_moisture", 20.0, "estaca", False),
                ("soil_ph", 6.4, "simulado", True),
                ("rainfall", 68.5, "nasa_power", False),
            ]
        ],
    }

    evaluation = AICropEvaluationOutput.model_validate(data)

    assert evaluation.evaluation_status == "incomplete"
    assert evaluation.recommendation_eligible is False


import pytest


@pytest.mark.asyncio
async def test_simulated_moisture_does_not_generate_advice():
    from datetime import date, datetime, timezone
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from uuid import uuid4

    from app.services.recommendation_service import RecommendationService
    from app.schemas.recommendations import RecommendationRunRequest

    parcel_id = uuid4()
    user_id = uuid4()

    service = RecommendationService.__new__(RecommendationService)

    repo = SimpleNamespace(
        get_parcel_context=AsyncMock(return_value={
            "soil_texture": "loam",
            "latest_weather_dt": date(2026, 11, 12),
        }),
        get_window_aggregates=AsyncMock(return_value={
            "soil": {
                "soil_temp_avg": 23.5,
                "soil_moisture_avg": 14.0,
            },
            "ph": None,
            "rainfall": {"precip_total_mm": 68.5},
        }),
        get_crop_requirements_bundle=AsyncMock(return_value=[{
            "crop_id": 1,
            "common_name_es": "Maíz",
            "scientific_name": "Zea mays",
            "requirements": {
                "soil_moisture": {
                    "optimal_min": 18.5,
                    "optimal_max": 25.0,
                },
            },
        }]),
        insert_run=AsyncMock(return_value={
            "id": uuid4(),
            "created_at": datetime.now(timezone.utc),
        }),
        insert_result=AsyncMock(),
        get_advice_rule=AsyncMock(return_value={
            "id": 1,
            "message_es": "Aumentar humedad de {current} a {target}.",
        }),
        insert_check=AsyncMock(),
    )

    service.repo = repo

    checks = [
        {
            "variable": "soil_temperature",
            "measured": 23.5,
            "status": "in_range",
            "origin": "estaca",
            "is_simulated": True,
        },
        {
            "variable": "soil_moisture",
            "measured": 14.0,
            "status": "below",
            "origin": "estaca",
            "is_simulated": True,
            "target_value": 18.5,
        },
        {
            "variable": "soil_ph",
            "measured": None,
            "status": "not_evaluated",
            "origin": "simulado",
            "is_simulated": True,
        },
        {
            "variable": "rainfall",
            "measured": 68.5,
            "status": "in_range",
            "origin": "nasa_power",
            "is_simulated": False,
        },
    ]

    evaluation = SimpleNamespace(
        crop_id=1,
        variables_ok=2,
        classification="no_recomendado",
        evaluation_status="incomplete",
        recommendation_eligible=False,
        ml_suitability_score=None,
        projected_days=None,
        future_risk_summary=None,
        checks=[SimpleNamespace(target_value=None, **check) if "target_value" not in check else SimpleNamespace(**check) for check in checks],
    )

    service.ai_client = SimpleNamespace(
        evaluate_parcel=AsyncMock(return_value=SimpleNamespace(
            evaluations=[evaluation]
        ))
    )

    request = RecommendationRunRequest(
        parcel_id=parcel_id,
        include_simulated_soil=True,
    )

    result = await service.evaluate_and_persist(
        req=request,
        user_id=user_id,
    )

    moisture = next(
        check
        for check in result["results"][0]["checks"]
        if check["variable"] == "soil_moisture"
    )

    assert moisture["is_simulated"] is True
    assert moisture["advice_text"] is None
