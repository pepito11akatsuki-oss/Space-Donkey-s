import asyncio
from sqlalchemy import text
from app.core.database import engine

ORG_ID = "11111111-1111-1111-1111-111111111111"

async def main():
    async with engine.begin() as conn:

        await conn.execute(
            text("SELECT set_config('app.org_id', :org_id, true)"),
            {"org_id": ORG_ID}
        )

        result = await conn.execute(text("""
            SELECT
                current_user,
                session_user,
                current_setting('app.org_id', true) AS org_context
        """))

        row = result.mappings().one()

        print("\n=== VERIFICACION RLS AGROSTAKE ===")
        print("Usuario:", row["current_user"])
        print("Sesion:", row["session_user"])
        print("Organizacion:", row["org_context"])

    await engine.dispose()

asyncio.run(main())
