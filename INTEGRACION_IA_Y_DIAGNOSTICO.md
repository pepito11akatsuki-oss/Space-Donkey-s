# AgroStake — integración incremental del motor de IA

## Cambios de esta entrega

- Se implementó `IA/app.py` como servicio FastAPI.
- Se expone `POST /api/v1/agronomy/evaluate`, que coincide con el contrato de la guía técnica del proyecto.
- La evaluación exige las cuatro variables y conserva el origen de los datos.
- Los valores faltantes permanecen como `null` y `not_evaluated`; nunca se convierten a cero.
- La clasificación se determina estrictamente por cantidad de variables `in_range`.
- `target_value` devuelve el límite óptimo más cercano cuando una medición queda por debajo o por encima.
- Se corrigió `IA/requirements.txt`, que antes contenía comandos de shell y no era un archivo instalable.
- `iniciar_agrostake.bat` ahora inicia también el servicio de IA en el puerto 8001.
- Se agregó `tools/diagnostico_postgres_local.py`, una comprobación de solo lectura para ejecutar en el equipo donde está PostgreSQL.

## Pruebas realizadas en esta entrega

Desde `IA/`:

```powershell
python -m pip install -r requirements.txt
python -m pip install pytest httpx
python -m pytest -q test_app_contract.py
```

Resultado en el entorno de construcción: **3 pruebas aprobadas** (health, contrato/clasificación y dato faltante).

## Comprobación en tu Windows

1. Conserva tus archivos `.env` locales; no los compartas ni los subas al repositorio.
2. Abre PowerShell en la carpeta raíz del proyecto.
3. Instala dependencias de IA: `python -m pip install -r IA/requirements.txt`.
4. Comprueba PostgreSQL sin modificarlo: `python tools/diagnostico_postgres_local.py`.
5. Inicia el sistema con `iniciar_agrostake.bat`.
6. Comprueba `http://127.0.0.1:8001/health` y `http://127.0.0.1:8001/docs`.

El backend de negocio ya tiene `AI_ENGINE_URL=http://localhost:8001` en la configuración incluida en el proyecto.

## Límites explícitos

Esta entrega no afirma que PostgreSQL, MQTT, el ESP32 físico ni el frontend estén integrados de extremo a extremo: el entorno de construcción no puede acceder a los servicios locales de tu PC ni al dispositivo. Tampoco se ha conectado todavía el login React a la API real; el frontend contiene flujos de demostración. El siguiente paso es ejecutar el diagnóstico local, confirmar el esquema/rol real y después integrar autenticación y consultas de frontend con contratos verificados. No se ejecutan migraciones SQL ni se altera tu base de datos.
