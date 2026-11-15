from datetime import datetime, timedelta, timezone
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import DomainValidationError, NotFoundError
from app.integrations.nasa_power_client import NasaPowerClient
from app.repositories.climate_repo import ClimateRepository
from app.repositories.parcel_repo import ParcelRepository


class ClimateService:
    def __init__(self, db: AsyncSession, nasa_client: NasaPowerClient | None = None):
        self.parcel_repo = ParcelRepository(db)
        self.climate_repo = ClimateRepository(db)
        self.nasa_client = nasa_client or NasaPowerClient()

    async def sync_parcel_weather(self, parcel_id: UUID, days_back: int = 7) -> dict:
        parcel = await self.parcel_repo.get_by_id(parcel_id)
        if not parcel:
            raise NotFoundError("Parcela no encontrada.")
        if not parcel["climate_cell_id"]:
            raise DomainValidationError("La parcela no tiene coordenadas ni celda climática asignada.")

        cell = await self.climate_repo.get_cell_by_id(parcel["climate_cell_id"])
        if not cell:
            raise NotFoundError("Celda climática no encontrada.")

        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=days_back)

        records = await self.nasa_client.fetch_daily_weather(
            latitude=cell["center_lat"],
            longitude=cell["center_lon"],
            start_date=start_date,
            end_date=end_date,
        )
        saved = await self.climate_repo.upsert_weather_daily(cell["id"], records)
        return {
            "parcel_id": str(parcel_id),
            "cell_id": str(cell["id"]),
            "center_lat": float(cell["center_lat"]),
            "center_lon": float(cell["center_lon"]),
            "days_synced": saved,
        }