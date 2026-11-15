from datetime import date, datetime
from decimal import Decimal
from typing import Any
import httpx
from app.core.config import settings
from app.core.exceptions import ExternalServiceError


class NasaPowerClient:
    PARAMETERS = "PRECTOTCORR,T2M,RH2M,TS,GWETTOP,GWETROOT"

    def __init__(self, base_url: str = settings.NASA_POWER_BASE_URL, timeout: float = 20.0):
        self.base_url = base_url
        self.timeout = timeout

    @staticmethod
    def _clean_metric(
        raw_val: Any, min_val: float, max_val: float, decimals: int = 2
    ) -> Decimal | None:
        if raw_val is None:
            return None
        try:
            num = float(raw_val)
        except (TypeError, ValueError):
            return None
        # NASA POWER usa -999 para días sin dato o con latencia satelital
        if num <= -900.0 or num < min_val or num > max_val:
            return None
        return round(Decimal(str(num)), decimals)

    async def fetch_daily_weather(
        self,
        latitude: Decimal | float,
        longitude: Decimal | float,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        params = {
            "parameters": self.PARAMETERS,
            "community": "AG",
            "longitude": float(longitude),
            "latitude": float(latitude),
            "start": start_date.strftime("%Y%m%d"),
            "end": end_date.strftime("%Y%m%d"),
            "format": "JSON",
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(self.base_url, params=params)
                resp.raise_for_status()
                payload = resp.json()
        except httpx.TimeoutException as exc:
            raise ExternalServiceError("NASA POWER excedió el tiempo de espera.") from exc
        except httpx.HTTPError as exc:
            raise ExternalServiceError(f"Error consultando NASA POWER: {exc}") from exc

        param_block = payload.get("properties", {}).get("parameter", {})
        precip_map = param_block.get("PRECTOTCORR", {})
        if not precip_map:
            return []

        records: list[dict[str, Any]] = []
        for date_str in sorted(precip_map.keys()):
            obs_dt = datetime.strptime(date_str, "%Y%m%d").date()
            day_raw = {
                k: param_block.get(k, {}).get(date_str)
                for k in ("PRECTOTCORR", "T2M", "RH2M", "TS", "GWETTOP", "GWETROOT")
            }
            records.append(
                {
                    "obs_date": obs_dt,
                    "precip_mm": self._clean_metric(day_raw["PRECTOTCORR"], 0.0, 2000.0, 2),
                    "air_temp_c": self._clean_metric(day_raw["T2M"], -90.0, 60.0, 2),
                    "rel_humidity": self._clean_metric(day_raw["RH2M"], 0.0, 100.0, 2),
                    "skin_temp_c": self._clean_metric(day_raw["TS"], -90.0, 90.0, 2),
                    "soil_wetness_surface": self._clean_metric(day_raw["GWETTOP"], 0.0, 1.0, 3),
                    "soil_wetness_root": self._clean_metric(day_raw["GWETROOT"], 0.0, 1.0, 3),
                    "raw_payload": day_raw,
                }
            )
        return records