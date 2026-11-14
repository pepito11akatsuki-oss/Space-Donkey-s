"""
Simulador de estaca ESP32-C3 para pruebas físicas y de integración MQTT.
Publica telemetría simulada al broker MQTT de AgroStake.
"""
import os
import json
import time
import random
import paho.mqtt.client as mqtt  # type: ignore

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
DEVICE_UID = "ESP32C3-TEST-001"
TOPIC = f"agrostake/stakes/{DEVICE_UID}/telemetry"

def simulate_stake():
    client = mqtt.Client()
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()

    print(f"Simulador iniciado. Publicando en {TOPIC} cada 5 segundos...")
    try:
        while True:
            payload = {
                "device_uid": DEVICE_UID,
                "msg_id": f"msg_{int(time.time() * 1000)}",
                "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "transport": "wifi_mqtt",
                "soil_temperature_c": round(random.uniform(18.0, 28.0), 2),
                "soil_moisture_raw": random.randint(1500, 3800),
                "battery_v": round(random.uniform(3.4, 4.2), 2),
                "is_simulated": False
            }
            client.publish(TOPIC, json.dumps(payload))
            print(f"Enviado: {payload}")
            time.sleep(5)
    except KeyboardInterrupt:
        print("Simulador detenido.")
        client.loop_stop()

if __name__ == "__main__":
    simulate_stake()
