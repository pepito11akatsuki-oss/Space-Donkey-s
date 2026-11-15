from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

PAYLOAD = {
    "parcel_id": "c7b8a9d0-1234-5678-9abc-def012345678",
    "soil_texture": "loam",
    "windows": {"soil_window_days": 7, "rainfall_window_days": 30, "window_end": "2026-11-12"},
    "observed_variables": {
        "soil_temperature": {"value": 23.5, "unit": "°C", "origin": "estaca", "is_simulated": False},
        "soil_moisture": {"value": 14.0, "unit": "% vol", "origin": "estaca", "is_simulated": False},
        "soil_ph": {"value": 6.4, "unit": "pH", "origin": "simulado", "ph_method": "simulado", "is_simulated": True},
        "rainfall": {"value": 68.5, "unit": "mm", "origin": "nasa_power", "is_simulated": False},
    },
    "candidate_crops": [{
        "crop_id": 1, "common_name_es": "Maíz", "requirements": {
            "soil_temperature": {"optimal_min": 18, "optimal_max": 30, "unit": "°C"},
            "soil_moisture": {"optimal_min": 18.5, "optimal_max": 25, "unit": "% vol"},
            "soil_ph": {"optimal_min": 5.8, "optimal_max": 7, "unit": "pH"},
            "rainfall": {"optimal_min": 50, "optimal_max": 120, "unit": "mm"},
        }
    }]
}


def test_health():
    assert client.get('/health').status_code == 200


def test_contract_and_classification():
    response = client.post('/api/v1/agronomy/evaluate', json=PAYLOAD)
    assert response.status_code == 200, response.text
    ev = response.json()['evaluations'][0]
    assert ev['variables_ok'] == 3
    assert ev['classification'] == 'condicionado'
    assert len(ev['checks']) == 4
    moisture = next(c for c in ev['checks'] if c['variable'] == 'soil_moisture')
    assert moisture['status'] == 'below' and moisture['target_value'] == 18.5
    ph = next(c for c in ev['checks'] if c['variable'] == 'soil_ph')
    assert ph['origin'] == 'simulado' and ph['is_simulated'] is True
    rain = next(c for c in ev['checks'] if c['variable'] == 'rainfall')
    assert rain['origin'] == 'nasa_power'


def test_missing_data_is_not_evaluated_not_zero():
    payload = {**PAYLOAD, 'observed_variables': {**PAYLOAD['observed_variables'], 'soil_ph': {
        'value': None, 'unit': 'pH', 'origin': 'simulado', 'ph_method': 'simulado', 'is_simulated': True
    }}}
    ev = client.post('/api/v1/agronomy/evaluate', json=payload).json()['evaluations'][0]
    ph = next(c for c in ev['checks'] if c['variable'] == 'soil_ph')
    assert ph['status'] == 'not_evaluated' and ph['measured'] is None
    assert ev['variables_ok'] == 2 and ev['classification'] == 'no_recomendado'


def test_all_missing_data_is_incomplete():
    from copy import deepcopy

    payload = deepcopy(PAYLOAD)

    for observed in payload["observed_variables"].values():
        observed["value"] = None

    response = client.post("/api/v1/agronomy/evaluate", json=payload)

    assert response.status_code == 200, response.text

    evaluation = response.json()["evaluations"][0]

    assert evaluation["variables_ok"] == 0
    assert all(
        check["status"] == "not_evaluated"
        for check in evaluation["checks"]
    )

    assert evaluation["evaluation_status"] == "incomplete"
