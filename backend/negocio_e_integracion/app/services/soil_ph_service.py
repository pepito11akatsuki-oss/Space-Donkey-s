import asyncio
import json
from urllib.parse import urlencode
from urllib.request import urlopen

SOILGRIDS_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"


def _fetch_ph(latitude: float, longitude: float):
    params = urlencode({
        "lat": latitude,
        "lon": longitude,
        "property": "phh2o",
        "depth": "0-5cm",
        "value": "mean",
    })

    with urlopen(f"{SOILGRIDS_URL}?{params}", timeout=12) as response:
        data = json.load(response)

    layer = next(
        layer for layer in data["properties"]["layers"]
        if layer["name"] == "phh2o"
    )

    raw_value = layer["depths"][0]["values"]["mean"]

    if raw_value is None:
        return None

    factor = layer["unit_measure"]["d_factor"]
    return round(raw_value / factor, 2)


async def get_soil_ph(latitude: float, longitude: float):
    try:
        ph = await asyncio.to_thread(_fetch_ph, latitude, longitude)
    except Exception:
        ph = None

    if ph is not None:
        return {
            "ph": ph,
            "source": "soilgrids",
            "estimated": True,
            "simulated": False,
            "depth": "0-5cm",
        }

    return {
        "ph": 6.42,
        "source": "demo_simulation",
        "estimated": False,
        "simulated": True,
        "depth": None,
        "message": "Valor simulado para demostracion; no representa una medicion real.",
    }
