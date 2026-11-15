from app.repositories.recommendation_repo import RecommendationRepository


def make_checks(simulated_ph=False):
    return [
        {
            "variable": "soil_temperature",
            "measured": 23.5,
            "status": "in_range",
            "origin": "estaca",
            "is_simulated": False,
        },
        {
            "variable": "soil_moisture",
            "measured": 20.0,
            "status": "in_range",
            "origin": "estaca",
            "is_simulated": False,
        },
        {
            "variable": "soil_ph",
            "measured": 6.4,
            "status": "in_range",
            "origin": "simulado" if simulated_ph else "laboratorio",
            "is_simulated": simulated_ph,
        },
        {
            "variable": "rainfall",
            "measured": 68.5,
            "status": "in_range",
            "origin": "nasa_power",
            "is_simulated": False,
        },
    ]


def test_simulated_history_is_not_eligible():
    status, eligible = RecommendationRepository.evaluate_history_safety(
        make_checks(simulated_ph=True)
    )

    assert status == "incomplete"
    assert eligible is False


def test_verified_history_is_eligible():
    status, eligible = RecommendationRepository.evaluate_history_safety(
        make_checks(simulated_ph=False)
    )

    assert status == "complete"
    assert eligible is True


def test_missing_history_is_not_eligible():
    checks = make_checks()
    checks.pop()

    status, eligible = RecommendationRepository.evaluate_history_safety(checks)

    assert status == "incomplete"
    assert eligible is False


def test_estimated_origin_is_not_eligible():
    checks = make_checks()
    checks[0]["origin"] = "dataset_estimado"

    status, eligible = RecommendationRepository.evaluate_history_safety(checks)

    assert status == "incomplete"
    assert eligible is False