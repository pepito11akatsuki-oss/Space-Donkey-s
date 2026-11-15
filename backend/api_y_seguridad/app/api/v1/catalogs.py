from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_principal
from app.db.session import get_public_db

router = APIRouter(
    tags=["Catálogos Agronómicos"],
    dependencies=[Depends(get_current_principal)],
)


@router.get("/crops")
async def list_crops(db: AsyncSession = Depends(get_public_db)):
    rows = (await db.execute(text("SELECT * FROM crops ORDER BY id ASC"))).all()
    return [dict(r._mapping) for r in rows]


@router.get("/crops/{crop_id}")
async def get_crop_detail(crop_id: int, db: AsyncSession = Depends(get_public_db)):
    crop = (
        await db.execute(text("SELECT * FROM crops WHERE id = :cid"), {"cid": crop_id})
    ).first()
    if not crop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cultivo no encontrado en el catálogo",
        )

    reqs = (
        await db.execute(
            text("""
                SELECT crop_id, variable::text AS variable, abs_min, optimal_min,
                       optimal_max, abs_max, unit, method, source_id
                FROM crop_requirements
                WHERE crop_id = :cid
                ORDER BY variable
            """),
            {"cid": crop_id},
        )
    ).all()

    elements = (
        await db.execute(
            text("""
                SELECT cer.crop_id, cer.element_id, se.symbol, se.name_es, se.unit,
                       cer.optimal_min, cer.optimal_max, cer.source_id
                FROM crop_element_requirements cer
                JOIN soil_elements se ON se.id = cer.element_id
                WHERE cer.crop_id = :cid
                ORDER BY cer.element_id
            """),
            {"cid": crop_id},
        )
    ).all()

    irrigation = (
        await db.execute(
            text("SELECT * FROM crop_irrigation_params WHERE crop_id = :cid"),
            {"cid": crop_id},
        )
    ).first()

    return {
        "crop": dict(crop._mapping),
        "variable_requirements": [dict(r._mapping) for r in reqs],
        "element_requirements": [dict(e._mapping) for e in elements],
        "irrigation_params": dict(irrigation._mapping) if irrigation else None,
    }


@router.get("/catalogs/soil-textures")
async def list_soil_textures(db: AsyncSession = Depends(get_public_db)):
    rows = (
        await db.execute(
            text("""
                SELECT stc.code, stc.name_es,
                       swc.fc_min, swc.fc_max, swc.wp_min, swc.wp_max, swc.source_id
                FROM soil_texture_classes stc
                LEFT JOIN soil_water_characteristics swc ON swc.texture_code = stc.code
                ORDER BY stc.code
            """)
        )
    ).all()
    return [dict(r._mapping) for r in rows]


@router.get("/catalogs/soil-elements")
async def list_soil_elements(db: AsyncSession = Depends(get_public_db)):
    rows = (
        await db.execute(
            text("SELECT id, symbol, name_es, category, unit FROM soil_elements ORDER BY id")
        )
    ).all()
    return [dict(r._mapping) for r in rows]


@router.get("/catalogs/advice-rules")
async def list_advice_rules(db: AsyncSession = Depends(get_public_db)):
    rows = (
        await db.execute(
            text("""
                SELECT id, variable::text AS variable, status::text AS status,
                       message_es, source_id
                FROM advice_rules
                ORDER BY id
            """)
        )
    ).all()
    return [dict(r._mapping) for r in rows]
