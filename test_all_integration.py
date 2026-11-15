import os
import sys
import psycopg2

def test_db_connection():
    print("Testing PostgreSQL database connection...")
    dsn = "postgresql://postgres:123vaqueros.@localhost:5432/agrostake"
    try:
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        cur.execute("SELECT version();")
        db_version = cur.fetchone()
        print(f"SUCCESS: Connected to PostgreSQL! Version: {db_version[0]}")
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"WARNING: Database connection failed (is PostgreSQL running?): {e}")
        return False

def test_python_modules():
    print("Testing Python modules and scripts syntax...")
    modules = [
        "backend/iot_e_integracion_de_datos/calibration.py",
        "backend/iot_e_integracion_de_datos/nasa_sync.py",
        "backend/iot_e_integracion_de_datos/mqtt_consumer.py",
        "IA/predictor_agro.py",
        "IA/db_connector.py",
    ]
    for mod in modules:
        if os.path.exists(mod):
            try:
                with open(mod, "rb") as f:
                    compile(f.read(), mod, "exec")
                print(f"  [OK] Compiled {mod}")
            except Exception as e:
                print(f"  [ERROR] Failed to compile {mod}: {e}")
        else:
            print(f"  [MISSING] {mod}")

if __name__ == "__main__":
    print("=== AGROSTAKE / SPACE-DONKEY INTEGRATION VERIFICATION ===")
    test_db_connection()
    test_python_modules()
    print("=== VERIFICATION COMPLETE ===")
