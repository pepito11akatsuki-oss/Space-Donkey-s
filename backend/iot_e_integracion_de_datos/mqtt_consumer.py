"""
Consumidor MQTT para telemetría de estacas AgroStake (ESP32-C3 SuperMini).
Escucha el broker Mosquitto, valida payloads JSON, procesa calibración y guarda en soil_readings.
"""
import os
import json
import logging
import paho.mqtt.client as mqtt  # type: ignore
import psycopg2
from psycopg2.extras import RealDictCursor
from calibration import convert_soil_moisture

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "agrostake/stakes/+/telemetry")

DB_DSN = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/agrostake")

def get_db_connection():
    return psycopg2.connect(DB_DSN)

def get_active_calibration(cursor, stake_id: str, sensor_type: str):
    cursor.execute(
        """
        SELECT params FROM sensor_calibrations
        WHERE stake_id = %s AND sensor = %s AND is_current = true
        LIMIT 1;
        """,
        (stake_id, sensor_type)
    )
    row = cursor.fetchone()
    return row[0] if row else None

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logging.info("Conectado al broker MQTT exitosamente. Suscribiendo a %s", MQTT_TOPIC)
        client.subscribe(MQTT_TOPIC)
    else:
        logging.error("Error de conexión MQTT, código: %d", rc)

def on_message(client, userdata, msg):
    try:
        payload_str = msg.payload.decode("utf-8")
        data = json.loads(payload_str)
        logging.info("Recibido payload en tópico %s: %s", msg.topic, data)

        device_uid = data.get("device_uid")
        msg_id = data.get("msg_id")
        measured_at = data.get("measured_at")
        soil_temp = data.get("soil_temperature_c")
        soil_moist_raw = data.get("soil_moisture_raw")
        battery_v = data.get("battery_v")
        transport = data.get("transport", "wifi_mqtt")
        is_simulated = data.get("is_simulated", False)

        if not device_uid or not msg_id or not measured_at:
            logging.warning("Payload incompleto (falta device_uid, msg_id o measured_at): %s", data)
            return

        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 1. Obtener ID de la estaca por device_uid
                cur.execute("SELECT id, org_id FROM stakes WHERE device_uid = %s;", (device_uid,))
                stake_row = cur.fetchone()
                if not stake_row:
                    logging.warning("Estaca desconocida para device_uid: %s", device_uid)
                    return
                
                stake_id = stake_row["id"]
                org_id = stake_row["org_id"]

                # Fijar RLS org_id en la transacción
                cur.execute("SET LOCAL app.org_id = %s;", (str(org_id),))

                # 2. Calibración y conversión de humedad si soil_moisture_raw está presente
                soil_moist_pct = data.get("soil_moisture_pct")
                if soil_moist_raw is not None and soil_moist_pct is None:
                    cal_params = get_active_calibration(cur, stake_id, "soil_moisture")
                    if not cal_params:
                        # Parámetros por defecto según especificación estándar del sensor capacitivo
                        cal_params = {"adc_dry": 4095, "adc_wet": 1200}
                    soil_moist_pct = convert_soil_moisture(soil_moist_raw, cal_params)

                # 3. Guardar lectura en soil_readings (idempotente por UNIQUE (stake_id, msg_id))
                cur.execute(
                    """
                    INSERT INTO soil_readings (
                        stake_id, measured_at, msg_id, transport,
                        soil_temperature_c, soil_moisture_raw, soil_moisture_pct,
                        battery_v, is_simulated
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (stake_id, msg_id) DO NOTHING;
                    """,
                    (
                        stake_id, measured_at, msg_id, transport,
                        soil_temp, soil_moist_raw, soil_moist_pct,
                        battery_v, is_simulated
                    )
                )

                # Actualizar last_seen_at en stakes
                cur.execute(
                    """
                    UPDATE stakes SET last_seen_at = now(), last_transport = %s
                    WHERE id = %s;
                    """,
                    (transport, stake_id)
                )
                conn.commit()
                logging.info("Lectura procesada y almacenada para estaca %s (msg_id: %s)", device_uid, msg_id)

    except Exception as e:
        logging.error("Error procesando mensaje MQTT: %s", e)

def main():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    logging.info("Iniciando cliente MQTT en %s:%d...", MQTT_BROKER, MQTT_PORT)
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_forever()

if __name__ == "__main__":
    main()
