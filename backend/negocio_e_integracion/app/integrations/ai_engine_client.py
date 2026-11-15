from typing import Any
import httpx
from pydantic import ValidationError
from app.core.config import settings
from app.core.exceptions import ExternalServiceError
from app.schemas.recommendations import AIEngineResponse


class AIEngineClient:
    def __init__(self, base_url: str = settings.AI_ENGINE_URL, timeout: float = 15.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def evaluate_parcel(self, payload: dict[str, Any]) -> AIEngineResponse:
        url = f"{self.base_url}/api/v1/agronomy/evaluate"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                raw_data = response.json()
        except httpx.TimeoutException as exc:
            raise ExternalServiceError("El motor agronómico (IA) excedió el tiempo de espera.") from exc
        except httpx.HTTPError as exc:
            raise ExternalServiceError(f"Error de comunicación con el motor agronómico: {exc}") from exc

        try:
            return AIEngineResponse.model_validate(raw_data)
        except ValidationError as exc:
            raise ExternalServiceError(
                f"El motor agronómico devolvió una estructura inválida: {exc.errors()}"
            ) from exc