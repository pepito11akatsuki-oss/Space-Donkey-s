from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.repositories.recommendation_repo import RecommendationRepository


class FakeQueryResult:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return self

    def all(self):
        return self.rows


@pytest.mark.asyncio
async def test_history_returns_safety_indicators():
    parcel_id = uuid4()
    run_id = uuid4()

    runs = [{
        "id": run_id,
        "soil_window_days": 7,
        "rainfall_window_days": 30,
        "window_end": date(2026, 11, 12),
        "created_at": datetime.now(timezone.utc),
    }]

    results = [{
        "run_id": run_id,
        "crop_id": 1,
        "common_name_es": "Maíz",
        "scientific_name": "Zea mays",
        "variables_ok": 4,
        "classification": "recomendado",
        "ml_suitability_score": None,
        "projected_days": None,
        "future_risk_summary": None,
    }]

    checks = [
        {
            "run_id": run_id,
            "crop_id": 1,
            "variable": variable,
            "measured": value,
            "status": "in_range",
            "origin": origin,
            "is_simulated": simulated,
            "advice_template": None,
        }
        for variable, value, origin, simulated in [
            ("soil_temperature", 23.5, "estaca", False),
            ("soil_moisture", 20.0, "estaca", False),
            ("soil_ph", 6.4, "simulado", True),
            ("rainfall", 68.5, "nasa_power", False),
        ]
    ]

    db = SimpleNamespace(
        execute=AsyncMock(side_effect=[
            FakeQueryResult(runs),
            FakeQueryResult(results),
            FakeQueryResult(checks),
        ])
    )

    repo = RecommendationRepository(db)

    history = await repo.list_parcel_runs(parcel_id)

    assert len(history) == 1
    assert len(history[0]["results"]) == 1

    crop = history[0]["results"][0]

    assert crop["classification"] == "recomendado"
    assert crop["evaluation_status"] == "incomplete"
    assert crop["recommendation_eligible"] is False

    assert len(crop["checks"]) == 4
    assert db.execute.await_count == 3