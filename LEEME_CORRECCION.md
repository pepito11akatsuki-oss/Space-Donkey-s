# AgroStake - correccion de diagnostico y launcher

Reemplaza estos archivos en la raiz del proyecto, conservando carpetas:
- `tools/diagnostico_postgres_local.py`
- `iniciar_agrostake.bat`

El diagnostico ahora convierte el esquema `postgresql+asyncpg://` de SQLAlchemy a `postgresql://`, que entiende psycopg2. La prueba es de solo lectura.

Ejecuta desde PowerShell en la raiz:

```powershell
python tools/diagnostico_postgres_local.py
```

Luego inicia los servicios con `./iniciar_agrostake.bat`. La correccion del BAT evita que `&` se interprete como separador de comandos en CMD.

No compartas `.env`, contrasenas, tokens ni credenciales del ESP32. Como una contrasena aparecio en la salida pegada al chat, cambiala en PostgreSQL y actualiza los `.env` correspondientes.
