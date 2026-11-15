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