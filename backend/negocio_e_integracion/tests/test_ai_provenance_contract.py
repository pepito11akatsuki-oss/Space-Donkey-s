import pytest
from pydantic import ValidationError

from app.schemas.recommendations import AIEngineResponse


def make_response(variable=None, origin=None, complete=True):
    origins = {
        "soil_temperature": "estaca",
        "soil_moisture": "estaca",
        "soil_ph": "laboratorio",
        "rainfall": "nasa_power",
    }

    checks = [
        {
            "variable": name,
            "measured": 20,
            "status": "in_range",
            "origin": origin if name == variable else default_origin,
            "is_simulated": False,
        }
        for name, default_origin in origins.items()
    ]

    return {
        "evaluations": [{
            "crop_id": 999999,
            "variables_ok": 4,
            "classification": "recomendado",
            "evaluation_status": "complete" if complete else "incomplete",
            "recommendation_eligible": complete,
            "checks": checks,
        }]
    }


@pytest.mark.parametrize(
    "variable,origin",
    [
        ("soil_moisture", "simulado"),
        ("soil_temperature", "dataset_estimado"),
    ],
)
def test_unverified_origin_is_marked_simulated(variable, origin):
    payload = make_response(variable, origin, complete=False)

    result = AIEngineResponse.model_validate(payload)
    evaluation = result.evaluations[0]

    check = next(
        item for item in evaluation.checks
        if item.variable == variable
    )

    assert check.is_simulated is True
    assert evaluation.evaluation_status == "incomplete"
    assert evaluation.recommendation_eligible is False


def test_contradictory_eligibility_is_rejected():
    payload = make_response(
        "soil_moisture",
        "simulado",
        complete=True,
    )

    with pytest.raises(ValidationError):
        AIEngineResponse.model_validate(payload)


def test_verified_measurements_remain_eligible():
    result = AIEngineResponse.model_validate(make_response())
    evaluation = result.evaluations[0]

    assert evaluation.evaluation_status == "complete"
    assert evaluation.recommendation_eligible is True
    assert len(evaluation.checks) == 4