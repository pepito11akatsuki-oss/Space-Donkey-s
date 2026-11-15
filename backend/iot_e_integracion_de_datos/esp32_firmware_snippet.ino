/*
 * ESP32-C3 SuperMini - Firmware Snippet para AgroStake
 * Sensores: DS18B20 (Temperatura) en GPIO4 y Sensor Capacitivo (Humedad) en ADC A0/GPIO0.
 * Conexión: WiFi + MQTT (PubSubClient)
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <OneWire.h>
#include <DallasTemperature.h>

// Configuración de Red
const char* ssid = "TU_WIFI_SSID";
const char* password = "TU_WIFI_PASSWORD";
const char* mqtt_server = "IP_DE_TU_SERVIDOR_MQTT";
const int mqtt_port = 1883;

// Identificación
const char* device_uid = "ESP32C3-STAKE-001";
char topic[64];

WiFiClient espClient;
PubSubClient client(espClient);

// Pines de sensores
#const ONE_WIRE_BUS 4
OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);
const int soilMoisturePin = A0; // GPIO0 (ADC1_CH0)

void setup_wifi() {
  delay(10);
  Serial.println("Conectando a WiFi...");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi conectado.");
}

void reconnect() {
  while (!client.connected()) {
    Serial.print("Intentando conexión MQTT...");
    sprintf(topic, "agrostake/stakes/%s/telemetry", device_uid);
    if (client.connect(device_uid)) {
      Serial.println("conectado.");
    } else {
      Serial.print("falló, rc=");
      Serial.print(client.state());
      Serial.println(" reintentando en 5 segundos");
      delay(5000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  setup_wifi();
  client.setServer(mqtt_server, mqtt_port);
  sensors.begin();
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  // Leer sensores
  sensors.requestTemperatures();
  float soilTemp = sensors.getTempCByIndex(0);
  int soilMoistRaw = analogRead(soilMoisturePin);

  // Crear JSON payload
  unsigned long msgId = millis();
  String payload = "{";
  payload += "\"device_uid\":\"" + String(device_uid) + "\",";
  payload += "\"msg_id\":\"msg_" + String(msgId) + "\",";
  payload += "\"measured_at\":\"2026-06-17T12:00:00Z\",";
  payload += "\"transport\":\"wifi_mqtt\",";
  payload += "\"soil_temperature_c\":" + String(soilTemp, 2) + ",";
  payload += "\"soil_moisture_raw\":" + String(soilMoistRaw) + ",";
  payload += "\"battery_v\":3.72,";
  payload += "\"is_simulated\":false";
  payload += "}";

  sprintf(topic, "agrostake/stakes/%s/telemetry", device_uid);
  client.publish(topic, payload.c_str());
  Serial.println("Telemetría publicada: " + payload);

  // Deep sleep o delay (ej. cada 60 segundos para pruebas)
  delay(60000);
}
