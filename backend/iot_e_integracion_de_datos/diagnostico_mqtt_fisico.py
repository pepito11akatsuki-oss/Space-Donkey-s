"""
Herramienta de Diagnóstico en Tiempo Real para el Hardware Real (ESP32-C3 SuperMini).
Escucha el broker MQTT, valida mensajes de estacas físicas, comprueba existencia en la BD
y reporta métricas de salud (temperatura, humedad cruda/porcentual, batería, transporte).
"""
import os
import json
import logging
import paho.mqtt.client as mqtt  # type: ignore
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC = "agrostake/stakes/+/telemetry"
DB_DSN = os.getenv("DATABASE_URL", "postgresql://postgres:***@localhost:5432/agrostake")

def get_db_connection():
    return psycopg2.connect(DB_DSN)

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logging.info("ESTETOSCOPIO MQTT CONECTADO. Escuchando telemetría física en %s...", MQTT_TOPIC)
        client.subscribe(MQTT_TOPIC)
    else:
        logging.error("Fallo al conectar al broker MQTT. Código: %d", rc)

def on_message(client, userdata, msg):
    print("\n" + "="*60)
    print(f"[MQTT RX] Tópico: {msg.topic}")
    try:
        payload_str = msg.payload.decode("utf-8")
        data = json.loads(payload_str)
        print(json.dumps(data, indent=2))

        device_uid = data.get("device_uid")
        msg_id = data.get("msg_id")
        soil_temp = data.get("soil_temperature_c")
        soil_moist_raw = data.get("soil_moisture_raw")
        battery_v = data.get("battery_v")
        is_simulated = data.get("is_simulated", True)

        # Verificaciones de sanidad del hardware
        warnings = []
        if is_simulated:
            warnings.append("⚠️ Advertencia: El payload indica que 'is_simulated' es True (debería ser False para hardware real).")
        if soil_temp is None or soil_temp < -20 or soil_temp > 80:
            warnings.append(f"⚠️ Advertencia: Temperatura de suelo anómala o nula ({soil_temp}°C). Revisa la conexión del sensor DS18B20 en GPIO4.")
        if soil_moist_raw is None or soil_moist_raw < 0 or soil_moist_raw > 4095:
            warnings.append(f"⚠️ Advertencia: Lectura ADC fuera de rango (0-4095): {soil_moist_raw}. Revisa el pin analógico A0.")
        if battery_v is None or battery_v < 3.0:
            warnings.append(f"⚠️ Advertencia: Voltaje de batería bajo ({battery_v}V).")

        # Comprobar si la estaca está registrada en PostgreSQL
        try:
            with get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("SELECT id, name, org_id, active FROM stakes WHERE device_uid = %s;", (device_uid,))
                    stake = cur.fetchone()
                    if stake:
                        print(f"[BD OK] Estaca registrada en BD -> ID: {stake['id']}, Nombre: {stake['name']}, Activa: {stake['active']}")
                    else:
                        print(f"[BD ERROR] ❌ La estaca con device_uid '{device_uid}' NO está registrada en la tabla 'stakes' de PostgreSQL.")
        except Exception as db_err:
            print(f"[BD ERROR] No se pudo conectar a la Base de Datos: {db_err}")

        if warnings:
            print("\nDiagnóstico de Hardware:")
            for w in warnings:
                print(f"  {w}")
        else:
            print("\n[ESTADO] ✅ Hardware físico operando dentro de parámetros normales.")

    except json.JSONDecodeError:
        print("[ERROR] El mensaje recibido no es un JSON válido.")
    except Exception as e:
        print(f"[ERROR] Excepción procesando mensaje: {e}")
    print("="*60 + "\n")

def main():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    print(f"Iniciando Estetoscopio MQTT en {MQTT_BROKER}:{MQTT_PORT}...")
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_forever()
    except KeyboardInterrupt:
        print("\nDiagnóstico detenido por el usuario.")

if __name__ == "__main__":
    main()
