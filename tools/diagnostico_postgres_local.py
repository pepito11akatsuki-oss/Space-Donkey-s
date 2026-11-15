"""Diagnostico PostgreSQL de solo lectura para AgroStake.

Lee DATABASE_URL desde backend/negocio_e_integracion/.env.
Acepta URLs SQLAlchemy como postgresql+asyncpg:// y las convierte
a URI PostgreSQL compatible con psycopg2. No imprime credenciales.
Ejecutar desde la raiz: python tools/diagnostico_postgres_local.py
"""
from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / "backend" / "negocio_e_integracion" / ".env"

try:
    from dotenv import load_dotenv
    import psycopg2
except ImportError as exc:
    print(f"FALTA DEPENDENCIA: {exc}. Ejecuta: python -m pip install python-dotenv psycopg2-binary")
    sys.exit(2)

load_dotenv(ENV_FILE, override=True)
dsn = os.getenv("DATABASE_URL", "").strip()
if not dsn:
    print(f"ERROR: No se encontro DATABASE_URL en {ENV_FILE}")
    sys.exit(2)

# DATABASE_URL del backend usa el dialecto de SQLAlchemy + asyncpg.
# psycopg2/libpq acepta postgresql://, no postgresql+asyncpg://.
if dsn.startswith("postgresql+asyncpg://"):
    dsn = "postgresql://" + dsn[len("postgresql+asyncpg://"): ]
elif dsn.startswith("postgresql+psycopg2://"):
    dsn = "postgresql://" + dsn[len("postgresql+psycopg2://"): ]

EXPECTED = {
    "organizations", "users", "parcels", "crops", "stakes", "soil_readings",
    "recommendation_runs", "recommendation_results", "recommendation_checks",
    "weather_daily", "climate_cells", "soil_ph_observations", "advice_rules",
}
conn = None
try:
    conn = psycopg2.connect(dsn, connect_timeout=5)
    conn.set_session(readonly=True, autocommit=True)
    with conn.cursor() as cur:
        cur.execute("SELECT current_database(), current_user, version()")
        db, role, version = cur.fetchone()
        print(f"OK PostgreSQL: {db} | usuario: {role}")
        print(f"Version: {version.split(',')[0]}")

        cur.execute("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        superuser, bypass = cur.fetchone()
        print(f"Seguridad RLS: superuser={superuser}, bypassrls={bypass}")
        if superuser or bypass:
            print("ADVERTENCIA: este rol omite RLS; no debe usarse para operaciones multi-tenant.")

        cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
        present = {r[0] for r in cur.fetchall()}
        missing = sorted(EXPECTED - present)
        print(f"Tablas esperadas: {len(EXPECTED)-len(missing)}/{len(EXPECTED)} presentes")
        if missing:
            print("FALTAN: " + ", ".join(missing))

        function_names = ["auth_register_owner", "auth_get_user_by_email", "nasa_grid_center", "soil_window", "rainfall_window", "latest_weather_date"]
        cur.execute("""
            SELECT p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE n.nspname='public' AND p.proname = ANY(%s)
        """, (function_names,))
        funcs = {r[0] for r in cur.fetchall()}
        needed = set(function_names)
        print(f"Funciones de integracion: {len(funcs)}/{len(needed)} presentes")
        if needed - funcs:
            print("FALTAN: " + ", ".join(sorted(needed - funcs)))

        cur.execute("""
            SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='public' AND c.relname = ANY(%s)
        """, (["organizations", "users", "parcels", "stakes", "soil_readings"],))
        for table, rls, forced in cur.fetchall():
            print(f"RLS {table}: enabled={rls}, forced={forced}")

    if missing or (needed - funcs):
        sys.exit(1)
    print("DIAGNOSTICO BASICO COMPLETADO. No se modifico la base de datos.")
except Exception as exc:
    # No imprimir el DSN: podria contener usuario y contrasena.
    print(f"ERROR DE CONEXION/CONSULTA: {type(exc).__name__}: {exc}")
    sys.exit(1)
finally:
    if conn is not None:
        conn.close()
