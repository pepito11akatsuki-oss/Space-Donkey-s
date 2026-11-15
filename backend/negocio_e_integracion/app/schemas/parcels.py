from datetime import date
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field

ParcelCropStatus = Literal["planificado", "activo", "cosechado"]


class ParcelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    area_ha: Decimal | None = Field(default=None, gt=0)
    soil_texture: str | None = None


class ParcelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    area_ha: Decimal | None = Field(default=None, gt=0)
    soil_texture: str | None = None


class ParcelCropAssign(BaseModel):
    crop_id: int
    status: ParcelCropStatus = "planificado"
    sown_at: date | None = None