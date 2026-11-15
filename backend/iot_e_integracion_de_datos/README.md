# Backend IoT e Ingrasta de Datos - AgroStake (Hacka-NASA 2026)

Este módulo es responsable de recibir, validar, procesar y almacenar la telemetría de las estacas IoT (ESP32-C3 SuperMini) y los datos climáticos externos (NASA POWER).

## Arquitectura y Componentes

1. **`mqtt_consumer.py`**: Cliente MQTT conectado a un broker Eclipse Mosquitto. Escucha el tópico `agrostake/stakes/+/telemetry`, valida los payloads JSON, aplica idempotencia mediante `msg_id` y actualiza la tabla `soil_readings` en PostgreSQL cumpliendo con Row-Level Security (RLS).
2. **`calibration.py`**: Módulo de conversión de lecturas analógicas crudas (`soil_moisture_raw`, ADC 0-4095) a porcentaje volumétrico real (`soil_moisture_pct`) utilizando los parámetros de calibración de dos puntos almacenados en `sensor_calibrations`.
3. **`nasa_sync.py`**: Sincronizador diario que consulta la API de NASA POWER (MERRA-2) para cada celda climática (`climate_cells`), obteniendo precipitación (`PRECTOTCORR`) y variables meteorológicas de contexto (`T2M`, `RH2M`, `TS`, `GWETTOP`, `GWETROOT`), manejando valores `-999` como `NULL` y aplicando UPSERT en `weather_daily`.

## Requisitos y Configuración

- Python 3.10+
- PostgreSQL 15+ (con el esquema `agrostake_schema_v3_2.sql`)
- Dependencias: ver `requirements.txt` (`pip install -r requirements.txt`)

## Ejecución

```bash
# Iniciar consumidor MQTT
python mqtt_consumer.py

# Ejecutar sincronización NASA POWER
python nasa_sync.py
```
