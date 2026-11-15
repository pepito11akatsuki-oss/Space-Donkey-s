from datetime import datetime
from decimal import Decimal
import secrets
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentPrincipal, get_tenant_db, require_roles
from app.core.config import settings
from app.db.session import get_public_db

router = APIRouter(tags=["Estacas e Ingesta IoT"])

TransportKind = Literal["ble", "wifi_mqtt"]
SensorKind = Literal["soil_moisture", "soil_temperature"]


class StakeCreateRequest(BaseModel):
    parcel_id: UUID
    device_uid: str = Field(min_length=3, max_length=120)
    firmware_version: str | None = Field(default=None, max_length=60)
    is_active: bool = True


class StakeUpdateRequest(BaseModel):
    parcel_id: UUID | None = None
    firmware_version: str | None = Field(default=None, max_length=60)
    is_active: bool | None = None


class StakeOut(BaseModel):
    id: UUID
    org_id: UUID
    parcel_id: UUID | None = None
    device_uid: str
    firmware_version: str | None
    last_transport: str | None
    last_seen_at: datetime | None
    installed_at: datetime | None
    is_active: bool


class CalibrationCreateRequest(BaseModel):
    sensor: SensorKind
    method: str = Field(min_length=2, max_length=80)
    params: dict[str, Any] = Field(default_factory=dict)


class IoTTelemetryRequest(BaseModel):
    device_uid: str = Field(min_length=3, max_length=120)
    measured_at: datetime | None = None
    msg_id: str | None = Field(default=None, max_length=120)
    transport: TransportKind = "wifi_mqtt"
    soil_temperature_c: Decimal | None = Field(default=None, ge=-55, le=125)
    soil_moisture_raw: int | None = None
    soil_moisture_pct: Decimal | None = Field(default=None, ge=0, le=100)
    battery_v: Decimal | None = Field(default=None, ge=0, le=15)
    is_simulated: bool = False


def verify_iot_api_key(x_iot_api_key: str = Header(..., alias="X-IoT-API-Key")) -> None:
    if not secrets.compare_digest(x_iot_api_key, settings.IOT_INGEST_API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-IoT-API-Key inválida",
        )


@router.get("/stakes", response_model=list[StakeOut])
async def list_stakes(
    parcel_id: UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_tenant_db),
):
    if parcel_id:
        rows = (
            await db.execute(
                text("""
                    SELECT id, org_id, parcel_id, device_uid, firmware_version,
                           last_transport::text AS last_transport, last_seen_at,
                           installed_at, is_active
                    FROM stakes
                    WHERE parcel_id = :pid
                    ORDER BY installed_at DESC NULLS LAST
                """),
                {"pid": parcel_id},
            )
        ).all()
    else:
        rows = (
            await db.execute(
                text("""
                    SELECT id, org_id, parcel_id, device_uid, firmware_version,
                           last_transport::text AS last_transport, last_seen_at,
                           installed_at, is_active
                    FROM stakes
                    ORDER BY installed_at DESC NULLS LAST
                """)
            )
        ).all()
    return [StakeOut(**r._mapping) for r in rows]


@router.post("/stakes", response_model=StakeOut, status_code=status.HTTP_201_CREATED)
async def register_stake(
    body: StakeCreateRequest,
    principal: CurrentPrincipal = Depends(require_roles("owner", "agronomist")),
    db: AsyncSession = Depends(get_tenant_db),
):
    parcel = (
        await db.execute(text("SELECT 1 FROM parcels WHERE id = :pid"), {"pid": body.parcel_id})
    ).first()
    if not parcel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La parcela no existe en tu organización",
        )

    try:
        row = (
            await db.execute(
                text("""
                    INSERT INTO stakes (
                        org_id, parcel_id, device_uid, firmware_version, installed_at, is_active
                    )
                    VALUES (:oid, :pid, :uid, :fw, now(), :active)
                    RETURNING id, org_id, parcel_id, device_uid, firmware_version,
                              last_transport::text AS last_transport, last_seen_at,
                              installed_at, is_active
                """),
                {
                    "oid": principal.org_id,
                    "pid": body.parcel_id,
                    "uid": body.device_uid.strip(),
                    "fw": body.firmware_version,
                    "active": body.is_active,
                },
            )
        ).one()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una estaca registrada con ese device_uid",
        )
    return StakeOut(**row._mapping)


@router.patch("/stakes/{stake_id}", response_model=StakeOut)
async def update_stake(
    stake_id: UUID,
    body: StakeUpdateRequest,
    principal: CurrentPrincipal = Depends(require_roles("owner", "agronomist")),
    db: AsyncSession = Depends(get_tenant_db),
):
    try:
        row = (
            await db.execute(
                text("""
                    UPDATE stakes
                    SET parcel_id = COALESCE(:pid, parcel_id),
                        firmware_version = COALESCE(:fw, firmware_version),
                        is_active = COALESCE(:active, is_active)
                    WHERE id = :sid
                    RETURNING id, org_id, parcel_id, device_uid, firmware_version,
                              last_transport::text AS last_transport, last_seen_at,
                              installed_at, is_active
                """),
                {
                    "sid": stake_id,
                    "pid": body.parcel_id,
                    "fw": body.firmware_version,
                    "active": body.is_active,
                },
            )
        ).first()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Parcela destino inválida para tu organización",
        )

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Estaca no encontrada",
        )
    return StakeOut(**row._mapping)


@router.post("/stakes/{stake_id}/calibrations", status_code=status.HTTP_201_CREATED)
async def add_sensor_calibration(
    stake_id: UUID,
    body: CalibrationCreateRequest,
    principal: CurrentPrincipal = Depends(require_roles("owner", "agronomist")),
    db: AsyncSession = Depends(get_tenant_db),
):
    stake = (
        await db.execute(text("SELECT 1 FROM stakes WHERE id = :sid"), {"sid": stake_id})
    ).first()
    if not stake:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Estaca no encontrada",
        )

    await db.execute(
        text("""
            UPDATE sensor_calibrations
            SET is_current = false
            WHERE stake_id = :sid AND sensor = CAST(:sensor AS variable_code) AND is_current = true
        """),
        {"sid": stake_id, "sensor": body.sensor},
    )

    import json

    row = (
        await db.execute(
            text("""
                INSERT INTO sensor_calibrations (stake_id, sensor, method, params, is_current)
                VALUES (:sid, CAST(:sensor AS variable_code), :method, CAST(:params AS jsonb), true)
                RETURNING id, stake_id, sensor::text AS sensor, method, params, calibrated_at, is_current
            """),
            {
                "sid": stake_id,
                "sensor": body.sensor,
                "method": body.method,
                "params": json.dumps(body.params),
            },
        )
    ).one()
    return dict(row._mapping)


@router.post(
    "/iot/telemetry",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_iot_api_key)],
)
async def ingest_iot_telemetry(
    body: IoTTelemetryRequest,
    db: AsyncSession = Depends(get_public_db),
):
    ctx = (
        await db.execute(
            text("SELECT * FROM iot_resolve_stake_context(:uid)"),
            {"uid": body.device_uid.strip()},
        )
    ).first()

    if not ctx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dispositivo IoT no registrado",
        )
    if not ctx.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La estaca IoT está desactivada",
        )

    await db.execute(
        text("SELECT set_config('app.org_id', :oid, true)"),
        {"oid": str(ctx.org_id)},
    )

    inserted = (
        await db.execute(
            text("""
                INSERT INTO soil_readings (
                    stake_id, measured_at, msg_id, transport,
                    soil_temperature_c, soil_moisture_raw, soil_moisture_pct,
                    battery_v, is_simulated
                )
                VALUES (
                    :sid, COALESCE(:measured_at, now()), :msg_id,
                    CAST(:transport AS transport_kind),
                    :temp_c, :moist_raw, :moist_pct, :batt_v, :sim
                )
                ON CONFLICT DO NOTHING
                RETURNING id, measured_at, received_at
            """),
            {
                "sid": ctx.stake_id,
                "measured_at": body.measured_at,
                "msg_id": body.msg_id,
                "transport": body.transport,
                "temp_c": body.soil_temperature_c,
                "moist_raw": body.soil_moisture_raw,
                "moist_pct": body.soil_moisture_pct,
                "batt_v": body.battery_v,
                "sim": body.is_simulated,
            },
        )
    ).first()

    await db.execute(
        text("""
            UPDATE stakes
            SET last_seen_at = now(),
                last_transport = CAST(:transport AS transport_kind)
            WHERE id = :sid
        """),
        {"sid": ctx.stake_id, "transport": body.transport},
    )

    if body.battery_v is not None and body.battery_v < Decimal("3.30"):
        await db.execute(
            text("""
                INSERT INTO alerts (stake_id, parcel_id, kind, severity, payload)
                VALUES (
                    :sid, :pid, 'bateria_baja', 'aviso',
                    jsonb_build_object('battery_v', :batt_v, 'device_uid', :uid)
                )
                ON CONFLICT DO NOTHING
            """),
            {
                "sid": ctx.stake_id,
                "pid": ctx.parcel_id,
                "batt_v": float(body.battery_v),
                "uid": body.device_uid.strip(),
            },
        )

    if not inserted:
        return {
            "status": "duplicate_ignored",
            "stake_id": str(ctx.stake_id),
            "org_id": str(ctx.org_id),
        }

    return {
        "status": "ingested",
        "reading_id": str(inserted.id),
        "stake_id": str(ctx.stake_id),
        "org_id": str(ctx.org_id),
        "measured_at": inserted.measured_at,
    }
