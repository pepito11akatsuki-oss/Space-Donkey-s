from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentPrincipal, get_tenant_db, require_roles

router = APIRouter(prefix="/parcels", tags=["Parcelas y Cultivos"])

ParcelCropStatus = Literal["planificado", "activo", "cosechado"]


class ParcelCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    latitude: Decimal = Field(ge=-90, le=90)
    longitude: Decimal = Field(ge=-180, le=180)
    area_ha: Decimal | None = Field(default=None, gt=0)
    soil_texture: str | None = Field(default=None, max_length=40)


class ParcelUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    area_ha: Decimal | None = Field(default=None, gt=0)
    soil_texture: str | None = Field(default=None, max_length=40)


class ParcelOut(BaseModel):
    id: UUID
    org_id: UUID
    name: str
    latitude: Decimal
    longitude: Decimal
    area_ha: Decimal | None
    climate_cell_id: UUID | None
    soil_texture: str | None
    created_at: datetime


class ParcelCropCreateRequest(BaseModel):
    crop_id: int = Field(gt=0)
    status: ParcelCropStatus = "planificado"
    sown_at: date | None = None


class ParcelCropUpdateRequest(BaseModel):
    status: ParcelCropStatus | None = None
    sown_at: date | None = None


class ParcelCropOut(BaseModel):
    id: UUID
    parcel_id: UUID
    crop_id: int
    common_name_es: str
    scientific_name: str | None
    status: str
    sown_at: date | None
    created_at: datetime


@router.get("", response_model=list[ParcelOut])
async def list_parcels(db: AsyncSession = Depends(get_tenant_db)):
    rows = (
        await db.execute(
            text("""
                SELECT id, org_id, name, latitude, longitude, area_ha,
                       climate_cell_id, soil_texture, created_at
                FROM parcels
                ORDER BY created_at DESC
            """)
        )
    ).all()
    return [ParcelOut(**r._mapping) for r in rows]


@router.post("", response_model=ParcelOut, status_code=status.HTTP_201_CREATED)
async def create_parcel(
    body: ParcelCreateRequest,
    principal: CurrentPrincipal = Depends(require_roles("owner", "agronomist")),
    db: AsyncSession = Depends(get_tenant_db),
):
    cell = (
        await db.execute(
            text("""
                SELECT cc.id
                FROM climate_cells cc
                JOIN nasa_grid_center(:lat, :lon) g
                  ON cc.center_lat = g.center_lat AND cc.center_lon = g.center_lon
                LIMIT 1
            """),
            {"lat": body.latitude, "lon": body.longitude},
        )
    ).first()
    cell_id = cell.id if cell else None

    try:
        row = (
            await db.execute(
                text("""
                    INSERT INTO parcels (
                        org_id, name, latitude, longitude, area_ha, climate_cell_id, soil_texture
                    )
                    VALUES (:oid, :name, :lat, :lon, :area, :cell_id, :texture)
                    RETURNING id, org_id, name, latitude, longitude, area_ha,
                              climate_cell_id, soil_texture, created_at
                """),
                {
                    "oid": principal.org_id,
                    "name": body.name.strip(),
                    "lat": body.latitude,
                    "lon": body.longitude,
                    "area": body.area_ha,
                    "cell_id": cell_id,
                    "texture": body.soil_texture,
                },
            )
        ).one()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Textura de suelo inválida o restricción incumplida (revisa /catalogs/soil-textures)",
        )
    return ParcelOut(**row._mapping)


@router.get("/{parcel_id}")
async def get_parcel_detail(
    parcel_id: UUID,
    db: AsyncSession = Depends(get_tenant_db),
):
    parcel = (
        await db.execute(
            text("""
                SELECT id, org_id, name, latitude, longitude, area_ha,
                       climate_cell_id, soil_texture, created_at
                FROM parcels
                WHERE id = :pid
            """),
            {"pid": parcel_id},
        )
    ).first()
    if not parcel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parcela no encontrada",
        )

    soil_summary = (
        await db.execute(
            text("SELECT * FROM soil_window(:pid, CURRENT_DATE, 7, false)"),
            {"pid": parcel_id},
        )
    ).first()

    rain_summary = (
        await db.execute(
            text("SELECT * FROM rainfall_window(:pid, CURRENT_DATE, 30, 0.8)"),
            {"pid": parcel_id},
        )
    ).first()

    return {
        "parcel": ParcelOut(**parcel._mapping),
        "soil_window_7d": dict(soil_summary._mapping) if soil_summary else None,
        "rainfall_window_30d": dict(rain_summary._mapping) if rain_summary else None,
    }


@router.patch("/{parcel_id}", response_model=ParcelOut)
async def update_parcel(
    parcel_id: UUID,
    body: ParcelUpdateRequest,
    principal: CurrentPrincipal = Depends(require_roles("owner", "agronomist")),
    db: AsyncSession = Depends(get_tenant_db),
):
    try:
        row = (
            await db.execute(
                text("""
                    UPDATE parcels
                    SET name = COALESCE(:name, name),
                        latitude = COALESCE(:lat, latitude),
                        longitude = COALESCE(:lon, longitude),
                        area_ha = COALESCE(:area, area_ha),
                        soil_texture = COALESCE(:texture, soil_texture)
                    WHERE id = :pid
                    RETURNING id, org_id, name, latitude, longitude, area_ha,
                              climate_cell_id, soil_texture, created_at
                """),
                {
                    "pid": parcel_id,
                    "name": body.name.strip() if body.name else None,
                    "lat": body.latitude,
                    "lon": body.longitude,
                    "area": body.area_ha,
                    "texture": body.soil_texture,
                },
            )
        ).first()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valor inválido para soil_texture",
        )

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parcela no encontrada",
        )
    return ParcelOut(**row._mapping)


@router.delete("/{parcel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_parcel(
    parcel_id: UUID,
    principal: CurrentPrincipal = Depends(require_roles("owner")),
    db: AsyncSession = Depends(get_tenant_db),
):
    res = await db.execute(
        text("DELETE FROM parcels WHERE id = :pid RETURNING id"),
        {"pid": parcel_id},
    )
    if not res.first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parcela no encontrada",
        )


@router.get("/{parcel_id}/crops", response_model=list[ParcelCropOut])
async def list_parcel_crops(
    parcel_id: UUID,
    db: AsyncSession = Depends(get_tenant_db),
):
    rows = (
        await db.execute(
            text("""
                SELECT pc.id, pc.parcel_id, pc.crop_id,
                       c.common_name_es, c.scientific_name,
                       pc.status, pc.sown_at, pc.created_at
                FROM parcel_crops pc
                JOIN crops c ON c.id = pc.crop_id
                WHERE pc.parcel_id = :pid
                ORDER BY pc.created_at DESC
            """),
            {"pid": parcel_id},
        )
    ).all()
    return [ParcelCropOut(**r._mapping) for r in rows]


@router.post(
    "/{parcel_id}/crops",
    response_model=ParcelCropOut,
    status_code=status.HTTP_201_CREATED,
)
async def assign_crop_to_parcel(
    parcel_id: UUID,
    body: ParcelCropCreateRequest,
    principal: CurrentPrincipal = Depends(require_roles("owner", "agronomist")),
    db: AsyncSession = Depends(get_tenant_db),
):
    exists = (
        await db.execute(text("SELECT 1 FROM parcels WHERE id = :pid"), {"pid": parcel_id})
    ).first()
    if not exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parcela no encontrada en tu organización",
        )

    try:
        inserted = (
            await db.execute(
                text("""
                    INSERT INTO parcel_crops (parcel_id, crop_id, status, sown_at)
                    VALUES (:pid, :cid, :status, :sown_at)
                    RETURNING id
                """),
                {
                    "pid": parcel_id,
                    "cid": body.crop_id,
                    "status": body.status,
                    "sown_at": body.sown_at,
                },
            )
        ).one()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El cultivo no existe o ya está asignado con ese mismo estado a la parcela",
        )

    row = (
        await db.execute(
            text("""
                SELECT pc.id, pc.parcel_id, pc.crop_id,
                       c.common_name_es, c.scientific_name,
                       pc.status, pc.sown_at, pc.created_at
                FROM parcel_crops pc
                JOIN crops c ON c.id = pc.crop_id
                WHERE pc.id = :pcid
            """),
            {"pcid": inserted.id},
        )
    ).one()
    return ParcelCropOut(**row._mapping)


@router.patch("/{parcel_id}/crops/{parcel_crop_id}", response_model=ParcelCropOut)
async def update_parcel_crop(
    parcel_id: UUID,
    parcel_crop_id: UUID,
    body: ParcelCropUpdateRequest,
    principal: CurrentPrincipal = Depends(require_roles("owner", "agronomist")),
    db: AsyncSession = Depends(get_tenant_db),
):
    try:
        updated = (
            await db.execute(
                text("""
                    UPDATE parcel_crops
                    SET status = COALESCE(:status, status),
                        sown_at = COALESCE(:sown_at, sown_at)
                    WHERE id = :pcid AND parcel_id = :pid
                    RETURNING id
                """),
                {
                    "pcid": parcel_crop_id,
                    "pid": parcel_id,
                    "status": body.status,
                    "sown_at": body.sown_at,
                },
            )
        ).first()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe otro registro de este cultivo con el mismo estado en la parcela",
        )

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registro de cultivo en parcela no encontrado",
        )

    row = (
        await db.execute(
            text("""
                SELECT pc.id, pc.parcel_id, pc.crop_id,
                       c.common_name_es, c.scientific_name,
                       pc.status, pc.sown_at, pc.created_at
                FROM parcel_crops pc
                JOIN crops c ON c.id = pc.crop_id
                WHERE pc.id = :pcid
            """),
            {"pcid": updated.id},
        )
    ).one()
    return ParcelCropOut(**row._mapping)
