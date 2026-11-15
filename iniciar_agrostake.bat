@echo off
setlocal
TITLE AgroStake / Space-Donkey-s Launcher
COLOR 0A

echo ========================================================
echo       AGROSTAKE / SPACE-DONKEY SYSTEM LAUNCHER
echo ========================================================
echo [1/5] Iniciando Backend API y Seguridad (FastAPI)...
start "AgroStake API y Seguridad" cmd /k "cd /d %~dp0backend\api_y_seguridad && python -m uvicorn app.main:app --reload --port 8000"

echo [2/5] Iniciando Backend de Negocio e Integraciones (FastAPI)...
start "AgroStake Negocio" cmd /k "cd /d %~dp0backend\negocio_e_integracion && python -m uvicorn app.main:app --reload --port 8002"

echo [3/5] Iniciando Motor de IA Agronomica (FastAPI)...
start "AgroStake IA" cmd /k "cd /d %~dp0IA && python -m uvicorn app:app --reload --host 127.0.0.1 --port 8001"

echo [4/5] Iniciando Consumidor IoT / MQTT...
start "AgroStake IoT MQTT" cmd /k "cd /d %~dp0backend\iot_e_integracion_de_datos && python mqtt_consumer.py"

echo [5/5] Iniciando Frontend SPA (Vite + React)...
start "AgroStake Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo ========================================================
echo Todos los servicios han sido lanzados en ventanas separadas.
echo - Frontend: http://localhost:5173
echo - API y Seguridad: http://localhost:8000/docs
echo - Backend Negocio: http://localhost:8002/docs
echo - Motor IA: http://localhost:8001/docs
echo ========================================================
pause
endlocal
