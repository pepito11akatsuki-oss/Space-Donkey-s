# Reporte de Integración del Proyecto: Space-Donkey-s (AgroStake SaaS)

Este documento detalla la integración completa de los componentes desarrollados por el equipo para la plataforma multi-vertical AgroStake / Space-Donkey-s.

## 1. Arquitectura de Módulos

- **Frontend SPA (`frontend/`)**: 
  - Desarrollado en React + TypeScript + Vite con Tailwind/Lucide icons.
  - Interfaz completa para gestión de organizaciones, estacas IoT, telemetría en tiempo real, alertas, análisis con IA agronómica y asistente conversacional.
  - Compilado y verificado sin errores (`npm run build`).

- **Backend API & Seguridad (`backend/api_y_seguridad/`)**:
  - Construido con FastAPI, SQLAlchemy 2.0 y soporte PostgreSQL con Row-Level Security (RLS).
  - Incluye autenticación JWT, dependencias seguras y pruebas unitarias (`test_security.py`).

- **Negocio e Integración (`backend/negocio_e_integracion/`)**:
  - Repositorios y servicios de negocio (Alertas, Clima, Cultivos, Parcelas, Recomendaciones de siembra y Estacas).
  - Clientes de integración para la API de **NASA POWER** (datos climáticos y precipitación) y motor de IA.

- **IoT e Ingesta de Datos (`backend/iot_e_integracion_de_datos/`)**:
  - **`mqtt_consumer.py`**: Ingesta telemetría desde sensores ESP32-C3 vía MQTT (MQTT broker Mosquitto) con validación de carga y `msg_id` para idempotencia.
  - **`calibration.py`**: Conversión precisa de lecturas analógicas crudas (ADC 0-4095) a porcentaje volumétrico de humedad.
  - **`nasa_sync.py`**: Sincronizador automático diario con la API NASA POWER (MERRA-2).
  - Pruebas unitarias ejecutadas y aprobadas (`test_calibration.py`, `test_difficult_edge_cases.py`).

- **Módulo de IA & Modelos (`IA/`)**:
  - Modelos predictivos de cultivos (`modelo_cultivos.pkl`, `scaler_agro.pkl`), clasificador de intenciones NLP (`modelo_nlp_intencion.pkl`), conector a base de datos (`db_connector.py`) y servidor de predicción (`predictor_agro.py`).

- **Base de Datos (`base_de_datos/`)**:
  - Esquemas relacionales completos (`agrostake_v3_3_completo .sql`) con soporte multi-tenant, tipos ENUM (`transport_kind`, etc.) y políticas RLS.

---

## 2. Guía de Ejecución y Arranque

### Backend (APIs y Servicios Python)
1. Activar entorno virtual y ubicar dependencias:
   ```bash
   pip install -r backend/api_y_seguridad/requirements.txt
   pip install -r backend/negocio_e_integracion/requirements.txt
   pip install -r backend/iot_e_integracion_de_datos/requirements.txt
   pip install -r IA/requirements.txt
   ```
2. Ejecutar pruebas unitarias de IoT:
   ```bash
   python backend/iot_e_integracion_de_datos/test_calibration.py
   python backend/iot_e_integracion_de_datos/test_difficult_edge_cases.py
   ```
3. Iniciar API principal (FastAPI):
   ```bash
   uvicorn backend.api_y_seguridad.app.main:app --reload --port 8000
   ```

### Frontend (SPA React)
1. Instalar dependencias y levantar entorno de desarrollo o compilar:
   ```bash
   cd frontend
   npm install
   npm run dev      # Para desarrollo local
   npm run build    # Para compilación de producción
   ```

---
*Proyecto integrado y listo para su presentación y despliegue.*
