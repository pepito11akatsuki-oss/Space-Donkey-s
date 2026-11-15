import asyncio
from sqlalchemy import text
from app.core.database import engine

async def main():
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT
                current_user,
                session_user,
                current_setting('app.org_id', true) AS org_context
        """))

        row = result.mappings().one()

        print("\n=== CONEXION REAL DE AGROSTAKE ===")
        print("Usuario efectivo:", row["current_user"])
        print("Usuario de sesion:", row["session_user"])
        print("Organizacion:", row["org_context"])

    await engine.dispose()

asyncio.run(main())
