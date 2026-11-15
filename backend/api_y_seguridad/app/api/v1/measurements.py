from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentPrincipal, get_tenant_db, require_roles

router = APIRouter(prefix="/parcels/{parcel_id}", tags=["Mediciones y Clima"])

PhMethod = Literal["simulado", "kit_manual", "laboratorio", "dataset_estimado"]
SampleOrigin = Literal["laboratorio", "manual", "dataset"]


class PhObservationCreateRequest(BaseModel):
    stake_id: UUID | None = None
    observed_at: datetime | None = None
    ph: Decimal = Field(ge=0, le=14)
    method: PhMethod = "kit_manual"
    source_id: int | None = None
    notes: str | None = Field(default=None, max_length=500)


class SampleElementValue(BaseModel):
    element_id: int = Field(gt=0)
    value: Decimal


class SoilSampleCreateRequest(BaseModel):
    sampled_at: date
    depth_cm: Decimal = Field(gt=0, le=300)
    origin: SampleOrigin = "laboratorio"
    source_id: int | None = None
    values: list[SampleElementValue] = Field(default_factory=list)


@router.get("/readings")
async def get_parcel_soil_readings(
    parcel_id: UUID,
    include_simulated: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_tenant_db),
):
    rows = (
        await db.execute(
            text("""
                SELECT sr.id, sr.stake_id, s.device_uid, sr.measured_at, sr.received_at,
                       sr.transport::text AS transport, sr.soil_temperature_c,
                       sr.soil_moisture_raw, sr.soil_moisture_pct, sr.battery_v,
                       sr.is_simulated
                FROM soil_readings sr
                JOIN stakes s ON s.id = sr.stake_id
                WHERE s.parcel_id = :pid
                  AND (:inc_sim = true OR sr.is_simulated = false)
                ORDER BY sr.measured_at DESC
                LIMIT :lim
            """),
            {"pid": parcel_id, "inc_sim": include_simulated, "lim": limit},
        )
    ).all()
    return [dict(r._mapping) for r in rows]


@router.get("/ph")
async def list_parcel_ph_observations(
    parcel_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_tenant_db),
):
    rows = (
        await db.execute(
            text("""
                SELECT id, parcel_id, stake_id, observed_at, ph,
                       method::text AS method, entered_by, source_id, notes
                FROM soil_ph_observations
                WHERE parcel_id = :pid
                ORDER BY observed_at DESC
                LIMIT :lim
            """),
            {"pid": parcel_id, "lim": limit},
        )
    ).all()
    return [dict(r._mapping) for r in rows]


@router.post("/ph", status_code=status.HTTP_201_CREATED)
async def create_parcel_ph_observation(
    parcel_id: UUID,
    body: PhObservationCreateRequest,
    principal: CurrentPrincipal = Depends(require_roles("owner", "agronomist")),
    db: AsyncSession = Depends(get_tenant_db),
):
    if body.method == "dataset_estimado" and body.source_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="source_id es obligatorio cuando method es 'dataset_estimado'",
        )

    try:
        row = (
            await db.execute(
                text("""
                    INSERT INTO soil_ph_observations (
                        parcel_id, stake_id, observed_at, ph, method, entered_by, source_id, notes
                    )
                    VALUES (
                        :pid, :sid, COALESCE(:obs_at, now()), :ph,
                        CAST(:method AS ph_method), :uid, :src_id, :notes
                    )
                    RETURNING id, parcel_id, stake_id, observed_at, ph,
                              method::text AS method, entered_by, source_id, notes
                """),
                {
                    "pid": parcel_id,
                    "sid": body.stake_id,
                    "obs_at": body.observed_at,
                    "ph": body.ph,
                    "method": body.method,
                    "uid": principal.user_id,
                    "src_id": body.source_id,
                    "notes": body.notes,
                },
            )
        ).one()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Parcela, estaca o source_id inválido",
        )
    return dict(row._mapping)


@router.post("/soil-samples", status_code=status.HTTP_201_CREATED)
async def create_soil_sample(
    parcel_id: UUID,
    body: SoilSampleCreateRequest,
    principal: CurrentPrincipal = Depends(require_roles("owner", "agronomist")),
    db: AsyncSession = Depends(get_tenant_db),
):
    try:
        sample = (
            await db.execute(
                text("""
                    INSERT INTO soil_samples (parcel_id, sampled_at, depth_cm, origin, source_id)
                    VALUES (:pid, :sampled_at, :depth, :origin, :src_id)
                    RETURNING id, parcel_id, sampled_at, depth_cm, origin, source_id
                """),
                {
                    "pid": parcel_id,
                    "sampled_at": body.sampled_at,
                    "depth": body.depth_cm,
                    "origin": body.origin,
                    "src_id": body.source_id,
                },
            )
        ).one()

        for item in body.values:
            await db.execute(
                text("""
                    INSERT INTO soil_sample_values (sample_id, element_id, value)
                    VALUES (:sid, :eid, :val)
                """),
                {"sid": sample.id, "eid": item.element_id, "val": item.value},
            )
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Parcela, elemento químico o fuente inválida",
        )

    return {**dict(sample._mapping), "values_count": len(body.values)}


@router.get("/weather")
async def get_parcel_weather_history(
    parcel_id: UUID,
    limit: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_tenant_db),
):
    parcel = (
        await db.execute(
            text("SELECT climate_cell_id FROM parcels WHERE id = :pid"),
            {"pid": parcel_id},
        )
    ).first()
    if not parcel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parcela no encontrada",
        )
    if not parcel.climate_cell_id:
        return []

    rows = (
        await db.execute(
            text("""
                SELECT cell_id, obs_date, precip_mm, precip_product, air_temp_c,
                       rel_humidity, skin_temp_c, soil_wetness_surface,
                       soil_wetness_root, fetched_at
                FROM weather_daily
                WHERE cell_id = :cid
                ORDER BY obs_date DESC
                LIMIT :lim
            """),
            {"cid": parcel.climate_cell_id, "lim": limit},
        )
    ).all()
    return [dict(r._mapping) for r in rows]
