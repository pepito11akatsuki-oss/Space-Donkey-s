@echo off
TITLE AgroStake / Space-Donkey-s Launcher
COLOR 0A

echo ========================================================
echo       AGROSTAKE / SPACE-DONKEY SYSTEM LAUNCHER
echo ========================================================
echo [0/4] Instalando dependencias de FastAPI y Uvicorn...
python -m pip install fastapi uvicorn[standard] sqlalchemy psycopg-binary pydantic pydantic-settings pyjwt httpx paho-mqtt

echo [1/4] Iniciando Backend API y Seguridad (FastAPI)...
start "AgroStake API y Seguridad" cmd /k "cd /d %~dp0backend\api_y_seguridad && python -m uvicorn app.main:app --reload --port 8000"

echo [2/4] Iniciando Backend de Negocio e Integraciones (FastAPI)...
start "AgroStake Negocio" cmd /k "cd /d %~dp0backend\negocio_e_integracion && python -m uvicorn app.main:app --reload --port 8002"

echo [3/4] Iniciando Consumidor IoT / MQTT y Sincronizacion NASA...
start "AgroStake IoT MQTT" cmd /k "cd /d %~dp0backend\iot_e_integracion_de_datos && python mqtt_consumer.py"

echo [4/4] Iniciando Frontend SPA (Vite + React)...
start "AgroStake Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo ========================================================
echo ¡Todos los servicios han sido lanzados en ventanas separadas!
echo - Frontend: http://localhost:5173
echo - API & Seguridad: http://localhost:8000/docs
echo - Backend Negocio: http://localhost:8002/docs
echo ========================================================
pause
