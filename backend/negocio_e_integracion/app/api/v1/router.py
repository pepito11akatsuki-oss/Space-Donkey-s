from datetime import datetime, timedelta, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.core.security import CurrentUser, require_write_role
from app.repositories.alert_repo import AlertRepository
from app.repositories.analytics_repo import AnalyticsRepository
from app.repositories.crop_repo import CropRepository
from app.repositories.parcel_repo import ParcelRepository
from app.repositories.recommendation_repo import RecommendationRepository
from app.repositories.stake_repo import StakeRepository
from app.schemas.parcels import ParcelCreate, ParcelCropAssign, ParcelUpdate
from app.schemas.recommendations import RecommendationRunRequest
from app.services.alert_service import AlertService
from app.services.climate_service import ClimateService
from app.services.soil_ph_service import get_soil_ph
from app.services.recommendation_service import RecommendationService

api_router = APIRouter(prefix="/api/v1")


# --- Catálogos ---
@api_router.get("/crops", tags=["Catálogos"])
async def list_crops(soil_texture: str | None = None, db: AsyncSession = Depends(get_db)):
    return await CropRepository(db).list_crops(soil_texture=soil_texture)


@api_router.get("/soil-textures", tags=["Catálogos"])
async def list_textures(db: AsyncSession = Depends(get_db)):
    return await CropRepository(db).list_textures()


# --- Parcelas y Clima NASA POWER ---
@api_router.get("/parcels", tags=["Parcelas"])
async def list_parcels(db: AsyncSession = Depends(get_db)):
    return await ParcelRepository(db).list_all()


@api_router.post("/parcels", status_code=201, tags=["Parcelas"])
async def create_parcel(
    body: ParcelCreate,
    user: CurrentUser = Depends(require_write_role),
    db: AsyncSession = Depends(get_db),
):
    repo = ParcelRepository(db)
    cell_id = None
    if body.latitude is not None and body.longitude is not None:
        cell_id = await repo.resolve_climate_cell(body.latitude, body.longitude)

    parcel = await repo.create(
        org_id=user.org_id,
        name=body.name,
        latitude=body.latitude,
        longitude=body.longitude,
        area_ha=body.area_ha,
        soil_texture=body.soil_texture,
        climate_cell_id=cell_id,
    )
    # Precarga 35 días de lluvia desde NASA POWER si tiene coordenadas
    if cell_id is not None:
        try:
            await ClimateService(db).sync_parcel_weather(parcel["id"], days_back=35)
        except Exception:
            pass  # No bloquea el alta de la parcela si NASA POWER tarda
    return parcel


@api_router.get("/parcels/{parcel_id}", tags=["Parcelas"])
async def get_parcel(parcel_id: UUID, db: AsyncSession = Depends(get_db)):
    parcel = await ParcelRepository(db).get_by_id(parcel_id)
    if not parcel:
        raise NotFoundError("Parcela no encontrada.")
    return parcel


@api_router.patch("/parcels/{parcel_id}", tags=["Parcelas"])
async def update_parcel(
    parcel_id: UUID,
    body: ParcelUpdate,
    _: CurrentUser = Depends(require_write_role),
    db: AsyncSession = Depends(get_db),
):
    repo = ParcelRepository(db)
    updates = body.model_dump(exclude_unset=True)
    if updates.get("latitude") is not None and updates.get("longitude") is not None:
        updates["climate_cell_id"] = await repo.resolve_climate_cell(
            updates["latitude"], updates["longitude"]
        )
    updated = await repo.update(parcel_id, updates)
    if not updated:
        raise NotFoundError("Parcela no encontrada.")
    return updated


@api_router.post("/parcels/{parcel_id}/climate/sync", tags=["Parcelas"])
async def sync_parcel_climate(
    parcel_id: UUID,
    days_back: int = Query(default=7, ge=1, le=60),
    _: CurrentUser = Depends(require_write_role),
    db: AsyncSession = Depends(get_db),
):
    return await ClimateService(db).sync_parcel_weather(parcel_id=parcel_id, days_back=days_back)


@api_router.post("/parcels/{parcel_id}/crops", status_code=201, tags=["Parcelas"])
async def assign_crop_to_parcel(
    parcel_id: UUID,
    body: ParcelCropAssign,
    _: CurrentUser = Depends(require_write_role),
    db: AsyncSession = Depends(get_db),
):
    return await ParcelRepository(db).assign_crop(
        parcel_id=parcel_id, crop_id=body.crop_id, status=body.status, sown_at=body.sown_at
    )


@api_router.get("/parcels/{parcel_id}/crops", tags=["Parcelas"])
async def list_parcel_crops(parcel_id: UUID, db: AsyncSession = Depends(get_db)):
    return await ParcelRepository(db).list_crops(parcel_id)



@api_router.get("/parcels/{parcel_id}/soil/ph-estimate", tags=["Suelo"])
async def parcel_soil_ph_estimate(
    parcel_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    parcel = await ParcelRepository(db).get_by_id(parcel_id)

    if not parcel:
        raise NotFoundError("Parcela no encontrada.")

    latitude = parcel.get("latitude")
    longitude = parcel.get("longitude")

    if latitude is None or longitude is None:
        return {
            "parcel_id": str(parcel_id),
            "ph": None,
            "source": "unavailable",
            "simulated": False,
            "message": "La parcela no tiene coordenadas.",
        }

    result = await get_soil_ph(
        latitude=float(latitude),
        longitude=float(longitude),
    )

    return {
        "parcel_id": str(parcel_id),
        **result,
    }
# --- Estacas ---
@api_router.get("/stakes", tags=["Estacas"])
async def list_stakes(parcel_id: UUID | None = None, db: AsyncSession = Depends(get_db)):
    return await StakeRepository(db).list_stakes(parcel_id=parcel_id)


@api_router.patch("/stakes/{stake_id}/parcel/{parcel_id}", tags=["Estacas"])
async def link_stake_to_parcel(
    stake_id: UUID,
    parcel_id: UUID,
    _: CurrentUser = Depends(require_write_role),
    db: AsyncSession = Depends(get_db),
):
    stake = await StakeRepository(db).link_to_parcel(stake_id=stake_id, parcel_id=parcel_id)
    if not stake:
        raise NotFoundError("Estaca o parcela no encontrada en tu organización.")
    return stake


@api_router.get("/stakes/{stake_id}/readings", tags=["Estacas"])
async def get_stake_readings(
    stake_id: UUID, limit: int = Query(default=100, ge=1, le=1000), db: AsyncSession = Depends(get_db)
):
    return await StakeRepository(db).get_readings(stake_id=stake_id, limit=limit)


# --- Analítica e Historial ---
@api_router.get("/parcels/{parcel_id}/summary", tags=["Analítica"])
async def parcel_summary(parcel_id: UUID, db: AsyncSession = Depends(get_db)):
    summary = await AnalyticsRepository(db).get_parcel_summary(parcel_id)
    if not summary:
        raise NotFoundError("Parcela no encontrada.")
    return summary


@api_router.get("/parcels/{parcel_id}/history/soil", tags=["Analítica"])
async def soil_history(
    parcel_id: UUID, days: int = Query(default=7, ge=1, le=90), db: AsyncSession = Depends(get_db)
):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    return await AnalyticsRepository(db).get_soil_history(parcel_id=parcel_id, since=since)


@api_router.get("/parcels/{parcel_id}/history/ph", tags=["Analítica"])
async def ph_history(parcel_id: UUID, db: AsyncSession = Depends(get_db)):
    return await AnalyticsRepository(db).get_ph_history(parcel_id=parcel_id)


@api_router.get("/parcels/{parcel_id}/history/rainfall", tags=["Analítica"])
async def rainfall_history(
    parcel_id: UUID, days: int = Query(default=30, ge=1, le=365), db: AsyncSession = Depends(get_db)
):
    return await AnalyticsRepository(db).get_rainfall_history(parcel_id=parcel_id, days=days)


# --- Recomendaciones Agronómicas (Integración IA) ---
@api_router.post("/recommendations/evaluate", status_code=201, tags=["Recomendaciones"])
async def evaluate_recommendations(
    body: RecommendationRunRequest,
    user: CurrentUser = Depends(require_write_role),
    db: AsyncSession = Depends(get_db),
):
    return await RecommendationService(db=db).evaluate_and_persist(req=body, user_id=user.user_id)


@api_router.get("/parcels/{parcel_id}/recommendations", tags=["Recomendaciones"])
async def list_parcel_recommendations(
    parcel_id: UUID, limit: int = Query(default=10, ge=1, le=50), db: AsyncSession = Depends(get_db)
):
    return await RecommendationRepository(db).list_parcel_runs(parcel_id=parcel_id, limit=limit)


# --- Alertas ---
@api_router.get("/alerts", tags=["Alertas"])
async def list_alerts(
    only_open: bool = True, parcel_id: UUID | None = None, db: AsyncSession = Depends(get_db)
):
    return await AlertRepository(db).list_alerts(only_open=only_open, parcel_id=parcel_id)


@api_router.post("/alerts/scan-stale", tags=["Alertas"])
async def scan_stale_stakes(
    max_silence_hours: int = Query(default=24, ge=1, le=720),
    _: CurrentUser = Depends(require_write_role),
    db: AsyncSession = Depends(get_db),
):
    return await AlertService(db).scan_stale_stakes(max_silence_hours=max_silence_hours)


@api_router.patch("/alerts/{alert_id}/resolve", tags=["Alertas"])
async def resolve_alert(
    alert_id: UUID,
    _: CurrentUser = Depends(require_write_role),
    db: AsyncSession = Depends(get_db),
):
    alert = await AlertRepository(db).resolve(alert_id)
    if not alert:
        raise NotFoundError("Alerta no encontrada.")
    return alert
