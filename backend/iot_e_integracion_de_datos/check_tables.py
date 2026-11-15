import os
import psycopg2

password = os.getenv("DB_PASSWORD", "postgres")
try:
    conn = psycopg2.connect(
        dbname="agrostake",
        user="postgres",
        password=password,
        host="localhost",
        port=5432
    )
    cur = conn.cursor()
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public';")
    tables = cur.fetchall()
    print("\n¡Conexión exitosa! Tablas encontradas en 'agrostake':")
    for t in tables:
        print(f" - {t[0]}")
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error conectando a la base de datos: {e}")
