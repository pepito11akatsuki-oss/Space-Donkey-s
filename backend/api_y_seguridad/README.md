# AgroStake Core API & Seguridad (backend/api_y_seguridad)

Backend REST multi-tenant construido con FastAPI, SQLAlchemy 2.0, psycopg v3 y PostgreSQL (esquema v3.3 con FORCE ROW LEVEL SECURITY).

## Ejecucion local
1. Activar entorno: .\.venv\Scripts\Activate.ps1
2. Instalar dependencias: pip install -r requirements.txt
3. Configurar .env local con DATABASE_URL, JWT_SECRET_KEY e IOT_INGEST_API_KEY
4. Iniciar servidor: uvicorn app.main:app --reload
5. Documentacion interactiva: http://127.0.0.1:8000/docs

## Pruebas de seguridad
.\.venv\Scripts\python.exe -m pytest -v
