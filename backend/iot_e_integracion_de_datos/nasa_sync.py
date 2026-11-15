"""
Sincronizador de datos meteorológicos de NASA POWER (MERRA-2) para AgroStake.
Obtiene PRECTOTCORR, T2M, RH2M, TS, GWETTOP, GWETROOT por celda climática y realiza UPSERT.
"""
import os
import datetime
import logging
import json
import httpx
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

DB_DSN = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/agrostake")
NASA_POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"

def get_db_connection():
    return psycopg2.connect(DB_DSN)

def fetch_nasa_power_data(lat: float, lon: float, start_date: str, end_date: str):
    """
    Consulta la API de NASA POWER para una ubicación (lat, lon) y rango de fechas (YYYYMMDD).
    """
    params = {
        "parameters": "PRECTOTCORR,T2M,RH2M,TS,GWETTOP,GWETROOT",
        "community": "AG",
        "longitude": lon,
        "latitude": lat,
        "start": start_date,
        "end": end_date,
        "format": "JSON"
    }
    try:
        response = httpx.get(NASA_POWER_URL, params=params, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        return data.get("properties", {}).get("parameter", {})
    except Exception as e:
        logging.error(f"Error consultando NASA POWER para ({lat}, {lon}): {e}")
        return None

def sync_climate_cells():
    """
    Recorre todas las celdas climáticas registradas y actualiza los últimos 7 días
    (manejo de latencia y reintentos por -999).
    """
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, center_lat, center_lon FROM climate_cells WHERE source = 'nasa_power';")
            cells = cur.fetchall()

            # Rango: últimos 7 días hasta ayer (por latencia de MERRA-2)
            end_dt = datetime.date.today() - datetime.timedelta(days=1)
            start_dt = end_dt - datetime.timedelta(days=7)
            
            start_str = start_dt.strftime("%Y%m%d")
            end_str = end_dt.strftime("%Y%m%d")

            for cell in cells:
                cell_id = cell["id"]
                lat = float(cell["center_lat"])
                lon = float(cell["center_lon"])

                logging.info("Sincronizando celda %s (%f, %f) desde %s hasta %s", cell_id, lat, lon, start_str, end_str)
                params_data = fetch_nasa_power_data(lat, lon, start_str, end_str)
                if not params_data:
                    continue

                prectotcorr = params_data.get("PRECTOTCORR", {})
                t2m = params_data.get("T2M", {})
                rh2m = params_data.get("RH2M", {})
                ts = params_data.get("TS", {})
                gwettop = params_data.get("GWETTOP", {})
                gwetroot = params_data.get("GWETROOT", {})

                # Obtener todas las fechas devueltas
                all_dates = set(prectotcorr.keys()) | set(t2m.keys()) | set(rh2m.keys())

                for date_str in all_dates:
                    # Formato NASA POWER fecha YYYYMMDD -> YYYY-MM-DD
                    try:
                        obs_date = datetime.datetime.strptime(date_str, "%Y%m%d").date()
                    except ValueError:
                        continue

                    def clean_val(val):
                        if val is None or val == -999 or val == -999.0:
                            return None
                        return val

                    p_mm = clean_val(prectotcorr.get(date_str))
                    air_t = clean_val(t2m.get(date_str))
                    rel_h = clean_val(rh2m.get(date_str))
                    skin_t = clean_val(ts.get(date_str))
                    soil_w_top = clean_val(gwettop.get(date_str))
                    soil_w_root = clean_val(gwetroot.get(date_str))

                    raw_payload_json = json.dumps({
                        "PRECTOTCORR": prectotcorr.get(date_str),
                        "T2M": t2m.get(date_str),
                        "RH2M": rh2m.get(date_str),
                        "TS": ts.get(date_str),
                        "GWETTOP": gwettop.get(date_str),
                        "GWETROOT": gwetroot.get(date_str)
                    })

                    cur.execute(
                        """
                        INSERT INTO weather_daily (
                            cell_id, obs_date, precip_mm, precip_product,
                            air_temp_c, rel_humidity, skin_temp_c,
                            soil_wetness_surface, soil_wetness_root, raw_payload
                        ) VALUES (%s, %s, %s, 'merra2_prectotcorr', %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (cell_id, obs_date) DO UPDATE SET
                            precip_mm = EXCLUDED.precip_mm,
                            air_temp_c = EXCLUDED.air_temp_c,
                            rel_humidity = EXCLUDED.rel_humidity,
                            skin_temp_c = EXCLUDED.skin_temp_c,
                            soil_wetness_surface = EXCLUDED.soil_wetness_surface,
                            soil_wetness_root = EXCLUDED.soil_wetness_root,
                            raw_payload = EXCLUDED.raw_payload,
                            fetched_at = now();
                        """,
                        (
                            cell_id, obs_date, p_mm,
                            air_t, rel_h, skin_t,
                            soil_w_top, soil_w_root, raw_payload_json
                        )
                    )
                conn.commit()
                logging.info("Celda %s sincronizada correctamente.", cell_id)

if __name__ == "__main__":
    sync_climate_cells()
