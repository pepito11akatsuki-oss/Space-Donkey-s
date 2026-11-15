import os
from contextlib import contextmanager
from typing import Dict, Any, List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()
# Usuario obligatorio según esquema v3.3: agrostake_app
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://agrostake_app:app_pass_local@localhost:5432/agrostake")


@contextmanager
def get_app_cursor(org_id: str):
    """Abre transacción como agrostake_app fijando app.org_id (FORCE RLS activo)."""
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SET LOCAL app.org_id = %s;", (str(org_id),))
                yield cur
    finally:
        conn.close()


def leer_insumos_parcela_v33(org_id: str, parcel_id: str, soil_days: int = 7, rain_days: int = 30) -> Dict[str, Any]:
    """Lee coordenadas, textura FAO-56, sensores (soil_window), lluvia NASA (rainfall_window) y último pH."""
    with get_app_cursor(org_id) as cur:
        cur.execute(
            "SELECT id, name, latitude, longitude, soil_texture, climate_cell_id FROM parcels WHERE id = %s;",
            (parcel_id,),
        )
        parcel = cur.fetchone()
        if not parcel:
            raise ValueError(f"Parcela {parcel_id} no existe o no pertenece a la organización.")

        # Fecha de corte basada en latest_weather_date()
        window_end = None
        if parcel["climate_cell_id"]:
            cur.execute("SELECT latest_weather_date(%s) AS w_end;", (parcel["climate_cell_id"],))
            row_w = cur.fetchone()
            window_end = row_w["w_end"] if row_w else None

        if not window_end:
            cur.execute("SELECT CURRENT_DATE AS hoy;")
            window_end = cur.fetchone()["hoy"]

        # Sensores estaca (excluye simulados por defecto)
        cur.execute("SELECT * FROM soil_window(%s, %s, %s, false);", (parcel_id, window_end, soil_days))
        soil = cur.fetchone() or {}

        # Lluvia NASA POWER (origin = 'nasa_power', NULL si cobertura < 80%)
        cur.execute("SELECT * FROM rainfall_window(%s, %s, %s, 0.8);", (parcel_id, window_end, rain_days))
        rain = cur.fetchone() or {}

        # Último pH (vista latest_soil_ph)
        cur.execute("SELECT observation_id, ph, method FROM latest_soil_ph WHERE parcel_id = %s;", (parcel_id,))
        ph_row = cur.fetchone()

        # Catálogo de cultivos activos en BD
        cur.execute("SELECT id, common_name_es, dataset_label, cycle_days_min, cycle_days_max FROM crops ORDER BY id;")
        crops_db = cur.fetchall()

        # Reglas de consejo sembradas en v3.3
        cur.execute("SELECT id, variable, status, message_es FROM advice_rules;")
        advice_rules = {(r["variable"], r["status"]): r for r in cur.fetchall()}

        return {
            "parcel": dict(parcel),
            "window_end": window_end,
            "soil_temp_c": float(soil["soil_temp_avg"]) if soil.get("soil_temp_avg") is not None else None,
            "soil_moisture_pct": float(soil["soil_moisture_avg"]) if soil.get("soil_moisture_avg") is not None else None,
            "rainfall_mm": float(rain["precip_total_mm"]) if rain.get("precip_total_mm") is not None else None,
            "ph": float(ph_row["ph"]) if ph_row else None,
            "ph_method": ph_row["method"] if ph_row else None,
            "ph_observation_id": str(ph_row["observation_id"]) if ph_row else None,
            "crops_db": [dict(c) for c in crops_db],
            "advice_rules": advice_rules,
        }


def guardar_corrida_auditable_v33(
    org_id: str,
    parcel_id: str,
    window_end: Any,
    evaluaciones: List[Dict[str, Any]],
    user_id: Optional[str] = None,
    soil_days: int = 7,
    rain_days: int = 30,
) -> str:
    """
    Persiste recommendation_runs, recommendation_results (con score ML y días proyectados)
    y exactamente 4 recommendation_checks por cultivo para pasar los triggers diferidos de v3.3.
    """
    with get_app_cursor(org_id) as cur:
        cur.execute(
            """
            INSERT INTO recommendation_runs (parcel_id, soil_window_days, rainfall_window_days, window_end, created_by)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (parcel_id, soil_days, rain_days, window_end, user_id),
        )
        run_id = cur.fetchone()["id"]

        for ev in evaluaciones:
            cur.execute(
                """
                INSERT INTO recommendation_results
                (run_id, crop_id, variables_ok, classification, ml_suitability_score, projected_days, future_risk_summary)
                VALUES (%s, %s, %s, %s, %s, %s, %s);
                """,
                (
                    run_id,
                    ev["crop_id"],
                    ev["variables_ok"],
                    ev["classification"],
                    ev.get("ml_suitability_score"),
                    ev.get("projected_days"),
                    ev.get("future_risk_summary"),
                ),
            )

            # Debe insertar exactamente las 4 variables (soil_temperature, soil_moisture, soil_ph, rainfall)
            for chk in ev["checks"]:
                measured_val = None if chk["status"] == "not_evaluated" else chk["measured"]
                cur.execute(
                    """
                    INSERT INTO recommendation_checks
                    (run_id, crop_id, variable, measured, status, origin, is_simulated, ph_observation_id, advice_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """,
                    (
                        run_id,
                        ev["crop_id"],
                        chk["variable"],
                        measured_val,
                        chk["status"],
                        chk.get("origin"),
                        chk.get("is_simulated", False),
                        chk.get("ph_observation_id"),
                        chk.get("advice_id"),
                    ),
                )

        return str(run_id)
