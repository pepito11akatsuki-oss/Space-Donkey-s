@echo off
TITLE Detener AgroStake / Space-Donkey-s
COLOR 0C

echo ========================================================
echo       CERRANDO SERVICIOS DE AGROSTAKE / SPACE-DONKEY
echo ========================================================

echo Deteniendo procesos de Python (Backends, MQTT, IA)...
taskkill /f /im python.exe 2>nul

echo Deteniendo procesos de Node.js (Frontend Vite)...
taskkill /f /im node.exe 2>nul

echo ========================================================
echo ¡Todos los servicios han sido detenidos correctamente!
echo ========================================================
pause
