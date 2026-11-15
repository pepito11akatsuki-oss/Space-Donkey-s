-- =====================================================================
-- AgroStake · BASE DE DATOS COMPLETA v3.3 (PostgreSQL 15+) · UN SOLO ARCHIVO
--
-- Ejecutar UNA vez, como SUPERUSUARIO, sobre un servidor sin la base agrostake:
--
--   psql -U postgres -v ON_ERROR_STOP=1 -f agrostake_v3_3_completo.sql
--   (opcional) -v owner_pass='CLAVE_OWNER' -v app_pass='CLAVE_APP'
--
-- Qué hace, en orden:
--   PARTE 1  Roles (owner, app, definer) y creación de la base `agrostake`
--   PARTE 2  Esquema v3.2 + módulo IA + parcel_crops + alertas por parcela
--            + FORCE RLS + funciones SECURITY DEFINER + permisos + correcciones
--            + parche v3.3.1 (origin dataset_estimado, alertas abiertas únicas)
--   PARTE 3  Semillas demo de cultivos (VALORES APROXIMADOS, no validados)
--   PARTE 4  Verificación automática (termina en ROLLBACK, no deja datos).
--            Si todo está bien imprime: TODAS LAS PRUEBAS OK
--
-- Los backends deben conectarse como `agrostake_app` y fijar en cada
-- transacción:  SET LOCAL app.org_id = '<org_id del JWT>';
-- No es re-ejecutable: para reiniciar, DROP DATABASE agrostake y vuelve a correrlo.
-- =====================================================================
\set ON_ERROR_STOP on

-- #####################################################################
-- PARTE 1 · ROLES Y BASE DE DATOS
-- #####################################################################


\if :{?owner_pass}
\else
  \set owner_pass 'owner_pass_local'
\endif
\if :{?app_pass}
\else
  \set app_pass 'app_pass_local'
\endif

SELECT format('CREATE ROLE agrostake_owner WITH LOGIN PASSWORD %L', :'owner_pass')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agrostake_owner') \gexec

SELECT format('CREATE ROLE agrostake_app WITH LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS', :'app_pass')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agrostake_app') \gexec

SELECT 'CREATE ROLE agrostake_definer NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE BYPASSRLS'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agrostake_definer') \gexec

-- El owner debe poder cederle la propiedad de las funciones al definer.
GRANT agrostake_definer TO agrostake_owner;

SELECT 'CREATE DATABASE agrostake OWNER agrostake_owner ENCODING ''UTF8'''
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'agrostake') \gexec

GRANT CONNECT ON DATABASE agrostake TO agrostake_app;


-- Cambiar a la base nueva y trabajar como dueño (los objetos quedan de agrostake_owner)
\connect agrostake
SET SESSION AUTHORIZATION agrostake_owner;

-- #####################################################################
-- PARTE 2 · ESQUEMA v3.3
-- #####################################################################
-- =====================================================================
-- AgroStake · Esquema CONSOLIDADO v3.3 (PostgreSQL 15+)
--
-- Incluye en un solo archivo, para una base NUEVA:
--   * Esquema base v3.2 (sin modificar, secciones 1-12)
--   * Módulo IA / proyección temporal (AgenteIA.txt)              -> sec. 13
--   * parcel_crops de la guía de acoplamiento                     -> sec. 14
--   * Alertas también por parcela (guía 1.2)                      -> sec. 15
--   * Funciones SECURITY DEFINER + FORCE RLS                      -> sec. 19-20
--   * Permisos mínimos del backend                                -> sec. 20
--   * CORRECCIONES detectadas al probar v3.2 + complementos       -> ver abajo
--
-- CORRECCIONES v3.3 respecto a v3.2 + complementos
--   1. FORCE RLS dejaba inservibles las funciones SECURITY DEFINER
--      (registro, login, refresh, resolución de estaca): ahora son de un
--      rol dedicado (agrostake_definer, BYPASSRLS).
--   2. El rol de la app podía escribir/borrar catálogos globales
--      (crops, advice_rules, data_sources...): ahora solo SELECT.
--   3. El motor aceptaba menos de 4 variables por cultivo: trigger diferido
--      que exige exactamente las 4 (guía 4.1).
--   4. Columnas de IA sin validación: CHECK 0-100, días > 0, min <= max.
--   5. rainfall_window devolvía origin 'merra2_prectotcorr'; el contrato
--      JSON espera 'nasa_power' (el producto va en la columna precip_product).
--   6. Reglas de consejo (advice_rules) para temperatura, pH y lluvia.
--   7. parcel_crops con FORCE RLS como el resto de tablas multi-tenant.
--
-- Uso (después de 00_roles_y_base.sql):
--   psql -U agrostake_owner -d agrostake -v ON_ERROR_STOP=1 -f 01_agrostake_schema_v3_3.sql
-- =====================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agrostake_app')
       OR NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agrostake_definer') THEN
        RAISE EXCEPTION 'Faltan los roles agrostake_app / agrostake_definer. Ejecuta primero 00_roles_y_base.sql como superusuario.';
    END IF;
    IF current_user <> 'agrostake_owner' THEN
        RAISE WARNING 'Se recomienda ejecutar este script como agrostake_owner (usuario actual: %).', current_user;
    END IF;
END $$;

-- =====================================================================
-- AgroStake · Esquema consolidado v3.2 (PostgreSQL 15+)
-- Hacka-NASA 2026
--
-- Úsalo en una base NUEVA. Reemplaza a agrostake_schema_v2, v3 y v3.1.
--
-- Decisiones de diseño
--  * Regla de viabilidad = 4 variables: temperatura del suelo, humedad del
--    suelo, pH y precipitación.
--      4/4 => recomendado | 3/4 => condicionado | <=2/4 => no recomendado
--    Esa clasificación vive en un CHECK: cambiarla requiere una migración.
--  * La estaca mide temperatura (DS18B20) y humedad capacitiva del suelo.
--  * El pH es SIMULADO (ph_method = 'simulado'); la UI debe etiquetarlo.
--  * La lluvia viene de NASA POWER (MERRA-2 PRECTOTCORR, mm/día) por celda de
--    0.5° lat x 0.625° lon. No hay pluviómetro físico.
--  * Ningún rango ni consejo existe sin fuente (data_sources).
--  * Una variable que no se pudo evaluar NO cuenta como "en rango".
--  * RLS multi-tenant en todas las tablas que contienen datos de clientes.
-- =====================================================================
CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid()

-- ---------------------------------------------------------------------
-- Tipos
-- ---------------------------------------------------------------------
CREATE TYPE user_role       AS ENUM ('owner', 'agronomist', 'viewer');
CREATE TYPE transport_kind  AS ENUM ('ble', 'wifi_mqtt');
CREATE TYPE weather_source  AS ENUM ('nasa_power', 'open_meteo');
CREATE TYPE ph_method       AS ENUM ('simulado', 'kit_manual', 'laboratorio', 'dataset_estimado');
CREATE TYPE viability_class AS ENUM ('recomendado', 'condicionado', 'no_recomendado');
CREATE TYPE variable_code   AS ENUM ('soil_temperature', 'soil_moisture', 'soil_ph', 'rainfall');
CREATE TYPE check_status    AS ENUM ('in_range', 'below', 'above', 'not_evaluated');

-- Tenant actual (la API ejecuta:  SET LOCAL app.org_id = '<uuid>';)
CREATE FUNCTION app_org_id() RETURNS uuid
LANGUAGE sql STABLE AS
$$ SELECT NULLIF(current_setting('app.org_id', true), '')::uuid $$;

-- =====================================================================
-- 1. TENANCY: organizaciones y usuarios
-- =====================================================================
CREATE TABLE organizations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE users (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id         UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    email          TEXT NOT NULL UNIQUE,
    password_hash  TEXT NOT NULL,               -- argon2/bcrypt, nunca texto plano
    full_name      TEXT NOT NULL,
    role           user_role NOT NULL DEFAULT 'viewer',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_users_org ON users(org_id);

CREATE TABLE refresh_tokens (                   -- soporte JWT
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  TEXT NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL,
    revoked_at  TIMESTAMPTZ
);
CREATE INDEX idx_refresh_user ON refresh_tokens(user_id);

-- =====================================================================
-- 2. CATÁLOGOS DE REFERENCIA (cada dato con su fuente)
-- =====================================================================
CREATE TABLE data_sources (
    id        SERIAL PRIMARY KEY,
    name      TEXT NOT NULL UNIQUE,
    url       TEXT,
    citation  TEXT,                              -- texto de reconocimiento / licencia
    version   TEXT
);

CREATE TABLE crops (
    id               SERIAL PRIMARY KEY,
    common_name_es   TEXT NOT NULL,
    scientific_name  TEXT UNIQUE,
    dataset_label    TEXT UNIQUE,                -- 'rice', 'maize'... (Dataset_Crop.csv)
    category         TEXT,
    source_id        INTEGER REFERENCES data_sources(id)
);

-- Rangos por variable (temperatura del suelo, pH, precipitación).
-- La humedad del suelo se deriva de FAO-56: ver vista v_crop_moisture_range.
-- optimal_* define "en rango" para la regla de viabilidad.
CREATE TABLE crop_requirements (
    crop_id       INTEGER NOT NULL REFERENCES crops(id) ON DELETE CASCADE,
    variable      variable_code NOT NULL,
    abs_min       NUMERIC(8,2),
    optimal_min   NUMERIC(8,2) NOT NULL,
    optimal_max   NUMERIC(8,2) NOT NULL,
    abs_max       NUMERIC(8,2),
    unit          TEXT NOT NULL,                 -- '°C', '% vol', 'pH', 'mm'
    method        TEXT,                          -- ej. 'p05-p95 (n=100)'
    source_id     INTEGER NOT NULL REFERENCES data_sources(id),
    PRIMARY KEY (crop_id, variable),
    CHECK (optimal_min <= optimal_max),
    CHECK (abs_min IS NULL OR abs_min <= optimal_min),
    CHECK (abs_max IS NULL OR abs_max >= optimal_max)
);

-- Variables que forman la regla de viabilidad.
CREATE TABLE viability_rule_variables (
    variable  variable_code PRIMARY KEY
);
INSERT INTO viability_rule_variables VALUES
    ('soil_temperature'), ('soil_moisture'), ('soil_ph'), ('rainfall');

-- Elementos del suelo (N, P, K...): referencia, la estaca no los mide.
CREATE TABLE soil_elements (
    id        SERIAL PRIMARY KEY,
    symbol    TEXT NOT NULL UNIQUE,
    name_es   TEXT NOT NULL,
    category  TEXT NOT NULL CHECK (category IN
              ('macro_primario','macro_secundario','micro','materia_organica','otro')),
    unit      TEXT NOT NULL
);

CREATE TABLE crop_element_requirements (
    crop_id      INTEGER NOT NULL REFERENCES crops(id) ON DELETE CASCADE,
    element_id   INTEGER NOT NULL REFERENCES soil_elements(id),
    optimal_min  NUMERIC(10,3),
    optimal_max  NUMERIC(10,3),
    source_id    INTEGER REFERENCES data_sources(id),
    PRIMARY KEY (crop_id, element_id),
    CHECK (optimal_min IS NULL OR optimal_max IS NULL OR optimal_min <= optimal_max)
);

-- ---- FAO-56 (Allen et al., 1998): base de los umbrales de riego --------
-- Tabla 19: capacidad de campo (CC) y punto de marchitez (PM) por textura, en m3/m3.
CREATE TABLE soil_texture_classes (
    code     TEXT PRIMARY KEY,                   -- 'sand', 'loam', 'clay'...
    name_es  TEXT NOT NULL
);

CREATE TABLE soil_water_characteristics (
    texture_code  TEXT PRIMARY KEY REFERENCES soil_texture_classes(code),
    fc_min        NUMERIC(4,3),                  -- capacidad de campo (rango)
    fc_max        NUMERIC(4,3),
    wp_min        NUMERIC(4,3),                  -- punto de marchitez (rango)
    wp_max        NUMERIC(4,3),
    source_id     INTEGER REFERENCES data_sources(id),
    CHECK (fc_min IS NULL OR fc_max IS NULL OR fc_min <= fc_max),
    CHECK (wp_min IS NULL OR wp_max IS NULL OR wp_min <= wp_max)
);

-- Tabla 22: profundidad radicular y fracción de agotamiento p por cultivo.
-- Umbral de riego = CC - p * (CC - PM)   (humedad volumétrica, m3/m3)
CREATE TABLE crop_irrigation_params (
    crop_id               INTEGER PRIMARY KEY REFERENCES crops(id) ON DELETE CASCADE,
    root_depth_m_min      NUMERIC(4,2),
    root_depth_m_max      NUMERIC(4,2),
    depletion_fraction_p  NUMERIC(3,2) CHECK (depletion_fraction_p BETWEEN 0 AND 1),
    source_id             INTEGER REFERENCES data_sources(id)
);

-- Rango óptimo de humedad del suelo por cultivo y textura, derivado de FAO-56:
--   mínimo = CC - p * (CC - PM)   (umbral de riego)
--   máximo = CC                   (por encima, el agua drena)
-- Usa el punto medio de los rangos de CC y PM. Resultado en % volumétrico.
CREATE VIEW v_crop_moisture_range WITH (security_invoker = true) AS
SELECT ip.crop_id,
       w.texture_code,
       round(((fc - ip.depletion_fraction_p * (fc - wp)) * 100)::numeric, 1) AS optimal_min_pct,
       round((fc * 100)::numeric, 1)                                         AS optimal_max_pct,
       ip.source_id
FROM crop_irrigation_params ip
CROSS JOIN soil_water_characteristics w
CROSS JOIN LATERAL (SELECT (w.fc_min + w.fc_max) / 2 AS fc,
                           (w.wp_min + w.wp_max) / 2 AS wp) m
WHERE ip.depletion_fraction_p IS NOT NULL
  AND w.fc_min IS NOT NULL AND w.fc_max IS NOT NULL
  AND w.wp_min IS NOT NULL AND w.wp_max IS NOT NULL;

-- Plantillas de retroalimentación explicable. Admiten {target} y {current}.
CREATE TABLE advice_rules (
    id          SERIAL PRIMARY KEY,
    variable    variable_code NOT NULL,
    status      check_status  NOT NULL CHECK (status IN ('below', 'above')),
    message_es  TEXT NOT NULL,
    source_id   INTEGER NOT NULL REFERENCES data_sources(id),
    UNIQUE (variable, status)
);

-- =====================================================================
-- 3. CLIMA POR CELDA (NASA POWER ~0.5° x 0.625°: varias parcelas comparten celda)
-- =====================================================================
CREATE TABLE climate_cells (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source      weather_source NOT NULL,
    center_lat  NUMERIC(8,4) NOT NULL,
    center_lon  NUMERIC(8,4) NOT NULL,
    UNIQUE (source, center_lat, center_lon)
);

-- Centro de la celda de NASA POWER (MERRA-2) que contiene un punto.
CREATE OR REPLACE FUNCTION nasa_grid_center(p_lat NUMERIC, p_lon NUMERIC)
RETURNS TABLE (center_lat NUMERIC, center_lon NUMERIC)
LANGUAGE sql IMMUTABLE AS $$
    SELECT round(p_lat / 0.5) * 0.5, round(p_lon / 0.625) * 0.625;
$$;

-- Clima diario por celda de NASA POWER (malla MERRA-2, 0.5° lat x 0.625° lon).
-- Reglas de ingesta:
--   * obs_date = make_date(YEAR, 1, 1) + (DOY - 1), siempre en hora UTC
--   * -999 se guarda como NULL, nunca como 0 ni como -999
--   * los últimos ~2 días llegan en -999 (latencia): volver a descargar y hacer
--     UPSERT de los últimos 7 días en cada ejecución.
CREATE TABLE weather_daily (
    cell_id         UUID NOT NULL REFERENCES climate_cells(id) ON DELETE CASCADE,
    obs_date        DATE NOT NULL,
    -- Entra a la regla de viabilidad:
    precip_mm       NUMERIC(7,2) CHECK (precip_mm >= 0),               -- PRECTOTCORR, mm/día
    precip_product  TEXT NOT NULL DEFAULT 'merra2_prectotcorr',
    -- Contexto para el dashboard (NO entran a la regla):
    air_temp_c            NUMERIC(5,2) CHECK (air_temp_c BETWEEN -90 AND 60),        -- T2M
    rel_humidity          NUMERIC(5,2) CHECK (rel_humidity BETWEEN 0 AND 100),       -- RH2M
    skin_temp_c           NUMERIC(5,2) CHECK (skin_temp_c BETWEEN -90 AND 90),       -- TS
    soil_wetness_surface  NUMERIC(4,3) CHECK (soil_wetness_surface BETWEEN 0 AND 1), -- GWETTOP
    soil_wetness_root     NUMERIC(4,3) CHECK (soil_wetness_root BETWEEN 0 AND 1),    -- GWETROOT
    raw_payload     JSONB,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (cell_id, obs_date)
);
CREATE INDEX idx_weather_daily_date ON weather_daily(obs_date DESC);

-- =====================================================================
-- 4. PARCELAS Y ESTACAS
-- =====================================================================
CREATE TABLE parcels (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id            UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name              TEXT NOT NULL,
    latitude          NUMERIC(9,6) CHECK (latitude  BETWEEN -90  AND 90),
    longitude         NUMERIC(9,6) CHECK (longitude BETWEEN -180 AND 180),
    area_ha           NUMERIC(10,2),
    climate_cell_id   UUID REFERENCES climate_cells(id),
    soil_texture      TEXT REFERENCES soil_texture_classes(code),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (id, org_id)                          -- permite FK compuestas entre organizaciones
);
CREATE INDEX idx_parcels_org          ON parcels(org_id);
CREATE INDEX idx_parcels_climate_cell ON parcels(climate_cell_id);

CREATE TABLE stakes (                            -- la estaca física
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id            UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    parcel_id         UUID,
    device_uid        TEXT NOT NULL UNIQUE,      -- ID del ESP32-C3 / topic MQTT
    firmware_version  TEXT,
    last_transport    transport_kind,
    last_seen_at      TIMESTAMPTZ,
    installed_at      TIMESTAMPTZ,
    is_active         BOOLEAN NOT NULL DEFAULT true,
    FOREIGN KEY (parcel_id, org_id) REFERENCES parcels(id, org_id) ON DELETE SET NULL (parcel_id)
);
CREATE INDEX idx_stakes_org    ON stakes(org_id);
CREATE INDEX idx_stakes_parcel ON stakes(parcel_id);

-- Calibración de los sensores crudos (ADC) a unidades reales.
CREATE TABLE sensor_calibrations (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stake_id       UUID NOT NULL REFERENCES stakes(id) ON DELETE CASCADE,
    sensor         variable_code NOT NULL CHECK (sensor IN ('soil_moisture', 'soil_temperature')),
    method         TEXT NOT NULL,                -- ej. 'dos_puntos_seco_agua'
    params         JSONB NOT NULL,
    calibrated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_current     BOOLEAN NOT NULL DEFAULT true
);
CREATE UNIQUE INDEX uq_calibration_current
    ON sensor_calibrations(stake_id, sensor) WHERE is_current;

-- =====================================================================
-- 5. SERIES DE TIEMPO
-- =====================================================================
-- Un payload JSON de la estaca = una fila. NULL si un sensor falló.
-- Usa id UUID como PK y (stake_id, msg_id) UNIQUE para evitar colisiones si el
-- reloj NTP del ESP32-C3 se reinicia tras perder conexión.
CREATE TABLE soil_readings (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    stake_id            UUID        NOT NULL REFERENCES stakes(id) ON DELETE CASCADE,
    measured_at         TIMESTAMPTZ NOT NULL,    -- hora del dispositivo (UTC)
    received_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    msg_id              TEXT        NOT NULL,    -- idempotencia ante reenvíos MQTT/BLE
    transport           transport_kind NOT NULL,
    soil_temperature_c  NUMERIC(5,2) CHECK (soil_temperature_c BETWEEN -55 AND 125),  -- rango DS18B20
    soil_moisture_raw   INTEGER,                 -- lectura analógica cruda (ADC)
    soil_moisture_pct   NUMERIC(5,2) CHECK (soil_moisture_pct BETWEEN 0 AND 100),     -- % volumétrico calibrado
    battery_v           NUMERIC(4,2),
    is_simulated        BOOLEAN NOT NULL DEFAULT false,
    UNIQUE (stake_id, msg_id)
);
CREATE INDEX idx_readings_stake_time ON soil_readings (stake_id, measured_at DESC);

-- =====================================================================
-- 6. pH Y MUESTRAS
-- =====================================================================
CREATE TABLE soil_ph_observations (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parcel_id    UUID NOT NULL REFERENCES parcels(id) ON DELETE CASCADE,
    stake_id     UUID REFERENCES stakes(id) ON DELETE SET NULL,
    observed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    ph           NUMERIC(4,2) NOT NULL CHECK (ph BETWEEN 0 AND 14),
    method       ph_method NOT NULL DEFAULT 'simulado',
    entered_by   UUID REFERENCES users(id),
    source_id    INTEGER REFERENCES data_sources(id),
    notes        TEXT,
    CHECK (method <> 'dataset_estimado' OR source_id IS NOT NULL)
);
CREATE INDEX idx_ph_obs_parcel ON soil_ph_observations(parcel_id, observed_at DESC);

CREATE VIEW latest_soil_ph WITH (security_invoker = true) AS
SELECT DISTINCT ON (parcel_id) id AS observation_id, parcel_id, ph, method, observed_at
FROM soil_ph_observations
ORDER BY parcel_id, observed_at DESC;

CREATE TABLE soil_samples (                      -- análisis de laboratorio / dataset
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parcel_id   UUID NOT NULL REFERENCES parcels(id) ON DELETE CASCADE,
    sampled_at  DATE NOT NULL,
    depth_cm    NUMERIC(5,1),
    origin      TEXT NOT NULL CHECK (origin IN ('laboratorio','manual','dataset')),
    source_id   INTEGER REFERENCES data_sources(id)
);
CREATE INDEX idx_samples_parcel ON soil_samples(parcel_id);

CREATE TABLE soil_sample_values (
    sample_id   UUID    NOT NULL REFERENCES soil_samples(id) ON DELETE CASCADE,
    element_id  INTEGER NOT NULL REFERENCES soil_elements(id),
    value       NUMERIC(12,4) NOT NULL,
    PRIMARY KEY (sample_id, element_id)
);

-- =====================================================================
-- 7. MOTOR DE RECOMENDACIÓN (auditable)
-- =====================================================================
CREATE TABLE recommendation_runs (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parcel_id             UUID NOT NULL REFERENCES parcels(id) ON DELETE CASCADE,
    soil_window_days      SMALLINT NOT NULL,     -- ventana para promediar temp/humedad del suelo
    rainfall_window_days  SMALLINT NOT NULL,     -- ventana para acumular lluvia
    window_end            DATE NOT NULL,         -- usar latest_weather_date(), no la fecha de hoy
    created_by            UUID REFERENCES users(id),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_runs_parcel ON recommendation_runs(parcel_id, created_at DESC);

CREATE TABLE recommendation_results (
    run_id          UUID     NOT NULL REFERENCES recommendation_runs(id) ON DELETE CASCADE,
    crop_id         INTEGER  NOT NULL REFERENCES crops(id),
    variables_ok    SMALLINT NOT NULL CHECK (variables_ok BETWEEN 0 AND 4),
    classification  viability_class NOT NULL,
    PRIMARY KEY (run_id, crop_id),
    CHECK (classification = CASE
              WHEN variables_ok = 4 THEN 'recomendado'::viability_class
              WHEN variables_ok = 3 THEN 'condicionado'::viability_class
              ELSE 'no_recomendado'::viability_class END)
);
CREATE INDEX idx_rec_results_crop ON recommendation_results(crop_id);

CREATE TABLE recommendation_checks (
    run_id            UUID NOT NULL,
    crop_id           INTEGER NOT NULL,
    variable          variable_code NOT NULL,
    measured          NUMERIC(8,2),                -- NULL si no se pudo evaluar
    status            check_status NOT NULL,
    origin            TEXT CHECK (origin IN ('estaca','nasa_power','simulado','manual','laboratorio')),
    is_simulated      BOOLEAN NOT NULL DEFAULT false,
    ph_observation_id UUID REFERENCES soil_ph_observations(id) ON DELETE SET NULL,
    advice_id         INTEGER REFERENCES advice_rules(id),
    PRIMARY KEY (run_id, crop_id, variable),
    FOREIGN KEY (run_id, crop_id) REFERENCES recommendation_results(run_id, crop_id) ON DELETE CASCADE,
    FOREIGN KEY (variable) REFERENCES viability_rule_variables(variable),
    CHECK ((status = 'not_evaluated' AND measured IS NULL)
        OR (status <> 'not_evaluated' AND measured IS NOT NULL))
);
CREATE INDEX idx_rec_checks_advice ON recommendation_checks(advice_id);

-- variables_ok debe coincidir con el número real de checks 'in_range'.
CREATE FUNCTION check_variables_ok() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_declared SMALLINT;
    v_actual   INT;
BEGIN
    SELECT variables_ok INTO v_declared
    FROM recommendation_results
    WHERE run_id = NEW.run_id AND crop_id = NEW.crop_id;
    IF NOT FOUND THEN RETURN NULL; END IF;

    SELECT count(*) INTO v_actual
    FROM recommendation_checks
    WHERE run_id = NEW.run_id AND crop_id = NEW.crop_id AND status = 'in_range';

    IF v_actual <> v_declared THEN
        RAISE EXCEPTION 'variables_ok (%) no coincide con checks in_range (%) para run % cultivo %',
            v_declared, v_actual, NEW.run_id, NEW.crop_id;
    END IF;
    RETURN NULL;
END $$;

CREATE CONSTRAINT TRIGGER trg_results_consistency
    AFTER INSERT OR UPDATE ON recommendation_results
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION check_variables_ok();

CREATE CONSTRAINT TRIGGER trg_checks_consistency
    AFTER INSERT OR UPDATE ON recommendation_checks
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION check_variables_ok();

-- =====================================================================
-- 8. ALERTAS Y SINCRONIZACIÓN OFFLINE
-- =====================================================================
CREATE TABLE alerts (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stake_id     UUID NOT NULL REFERENCES stakes(id) ON DELETE CASCADE,
    kind         TEXT NOT NULL CHECK (kind IN ('bateria_baja','sin_reporte','lectura_fuera_de_rango','humedad_baja')),
    severity     TEXT NOT NULL CHECK (severity IN ('info','aviso','critica')),
    payload      JSONB,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at  TIMESTAMPTZ
);
CREATE INDEX idx_alerts_open ON alerts(stake_id) WHERE resolved_at IS NULL;

CREATE TABLE sync_clients (                      -- cursores de sincronización (SQLite en cliente)
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    last_pull_at  TIMESTAMPTZ,
    last_push_at  TIMESTAMPTZ
);

-- =====================================================================
-- 9. FUNCIONES DE VENTANA (insumos del motor de recomendación)
-- =====================================================================
CREATE OR REPLACE FUNCTION soil_window(
    p_parcel UUID, p_end DATE, p_days INT DEFAULT 7, p_include_simulated BOOLEAN DEFAULT false)
RETURNS TABLE (soil_temp_avg NUMERIC, soil_moisture_avg NUMERIC, readings_count INT)
LANGUAGE sql STABLE AS $$
    SELECT round(avg(r.soil_temperature_c), 2),
           round(avg(r.soil_moisture_pct), 2),
           count(*)::int
    FROM soil_readings r
    JOIN stakes s ON s.id = r.stake_id
    WHERE s.parcel_id = p_parcel
      AND s.is_active
      AND r.measured_at >= ((p_end - p_days + 1)::timestamp AT TIME ZONE 'UTC')
      AND r.measured_at <  ((p_end + 1)::timestamp          AT TIME ZONE 'UTC')
      AND (p_include_simulated OR NOT r.is_simulated);
$$;

CREATE OR REPLACE FUNCTION latest_weather_date(p_cell UUID)
RETURNS DATE
LANGUAGE sql STABLE AS $$
    SELECT max(obs_date) FROM weather_daily WHERE cell_id = p_cell AND precip_mm IS NOT NULL;
$$;

CREATE OR REPLACE FUNCTION rainfall_window(
    p_parcel UUID, p_end DATE, p_days INT DEFAULT 30, p_min_coverage NUMERIC DEFAULT 0.8)
RETURNS TABLE (precip_total_mm NUMERIC, origin TEXT, days_with_data INT,
               window_days INT, last_valid_date DATE)
LANGUAGE sql STABLE AS $$
    SELECT CASE WHEN count(w.precip_mm) >= ceil(p_days * p_min_coverage)
                THEN round(sum(w.precip_mm), 2) END,
           COALESCE(max(w.precip_product), 'sin_datos'),
           count(w.precip_mm)::int,
           p_days,
           max(w.obs_date) FILTER (WHERE w.precip_mm IS NOT NULL)
    FROM parcels p
    JOIN climate_cells c ON c.id = p.climate_cell_id AND c.source = 'nasa_power'
    LEFT JOIN weather_daily w
           ON w.cell_id = c.id
          AND w.obs_date >  p_end - p_days
          AND w.obs_date <= p_end
    WHERE p.id = p_parcel;
$$;

-- =====================================================================
-- 10. SEGURIDAD MULTI-TENANT (Row-Level Security) Y AUTH HELPERS
-- La API fija el tenant por transacción:  SET LOCAL app.org_id = '<uuid>';
-- =====================================================================
ALTER TABLE organizations          ENABLE ROW LEVEL SECURITY;
ALTER TABLE users                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE refresh_tokens         ENABLE ROW LEVEL SECURITY;
ALTER TABLE sync_clients           ENABLE ROW LEVEL SECURITY;
ALTER TABLE parcels                ENABLE ROW LEVEL SECURITY;
ALTER TABLE stakes                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE sensor_calibrations    ENABLE ROW LEVEL SECURITY;
ALTER TABLE soil_readings          ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE soil_ph_observations   ENABLE ROW LEVEL SECURITY;
ALTER TABLE soil_samples           ENABLE ROW LEVEL SECURITY;
ALTER TABLE soil_sample_values     ENABLE ROW LEVEL SECURITY;
ALTER TABLE recommendation_runs    ENABLE ROW LEVEL SECURITY;
ALTER TABLE recommendation_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE recommendation_checks  ENABLE ROW LEVEL SECURITY;

-- Tablas con org_id propio
CREATE POLICY tenant_orgs ON organizations
    FOR ALL USING (id = app_org_id()) WITH CHECK (id = app_org_id());
CREATE POLICY tenant_users ON users
    FOR ALL USING (org_id = app_org_id()) WITH CHECK (org_id = app_org_id());
CREATE POLICY tenant_parcels ON parcels
    FOR ALL USING (org_id = app_org_id()) WITH CHECK (org_id = app_org_id());
CREATE POLICY tenant_stakes ON stakes
    FOR ALL USING (org_id = app_org_id()) WITH CHECK (org_id = app_org_id());

-- Tablas hijas: heredan el filtro del padre (con USING y WITH CHECK explícitos)
CREATE POLICY tenant_refresh ON refresh_tokens
    FOR ALL
    USING (EXISTS (SELECT 1 FROM users u WHERE u.id = user_id))
    WITH CHECK (EXISTS (SELECT 1 FROM users u WHERE u.id = user_id));

CREATE POLICY tenant_sync ON sync_clients
    FOR ALL
    USING (EXISTS (SELECT 1 FROM users u WHERE u.id = user_id))
    WITH CHECK (EXISTS (SELECT 1 FROM users u WHERE u.id = user_id));

CREATE POLICY tenant_calibrations ON sensor_calibrations
    FOR ALL
    USING (EXISTS (SELECT 1 FROM stakes s WHERE s.id = stake_id))
    WITH CHECK (EXISTS (SELECT 1 FROM stakes s WHERE s.id = stake_id));

CREATE POLICY tenant_readings ON soil_readings
    FOR ALL
    USING (EXISTS (SELECT 1 FROM stakes s WHERE s.id = stake_id))
    WITH CHECK (EXISTS (SELECT 1 FROM stakes s WHERE s.id = stake_id));

CREATE POLICY tenant_alerts ON alerts
    FOR ALL
    USING (EXISTS (SELECT 1 FROM stakes s WHERE s.id = stake_id))
    WITH CHECK (EXISTS (SELECT 1 FROM stakes s WHERE s.id = stake_id));

CREATE POLICY tenant_ph ON soil_ph_observations
    FOR ALL
    USING (EXISTS (SELECT 1 FROM parcels p WHERE p.id = parcel_id))
    WITH CHECK (EXISTS (SELECT 1 FROM parcels p WHERE p.id = parcel_id));

CREATE POLICY tenant_samples ON soil_samples
    FOR ALL
    USING (EXISTS (SELECT 1 FROM parcels p WHERE p.id = parcel_id))
    WITH CHECK (EXISTS (SELECT 1 FROM parcels p WHERE p.id = parcel_id));

CREATE POLICY tenant_sample_values ON soil_sample_values
    FOR ALL
    USING (EXISTS (SELECT 1 FROM soil_samples ss WHERE ss.id = sample_id))
    WITH CHECK (EXISTS (SELECT 1 FROM soil_samples ss WHERE ss.id = sample_id));

CREATE POLICY tenant_runs ON recommendation_runs
    FOR ALL
    USING (EXISTS (SELECT 1 FROM parcels p WHERE p.id = parcel_id))
    WITH CHECK (EXISTS (SELECT 1 FROM parcels p WHERE p.id = parcel_id));

CREATE POLICY tenant_run_results ON recommendation_results
    FOR ALL
    USING (EXISTS (SELECT 1 FROM recommendation_runs r WHERE r.id = run_id))
    WITH CHECK (EXISTS (SELECT 1 FROM recommendation_runs r WHERE r.id = run_id));

CREATE POLICY tenant_run_checks ON recommendation_checks
    FOR ALL
    USING (EXISTS (SELECT 1 FROM recommendation_runs r WHERE r.id = run_id))
    WITH CHECK (EXISTS (SELECT 1 FROM recommendation_runs r WHERE r.id = run_id));

-- Funciones SECURITY DEFINER para registro y login antes de contar con app.org_id
CREATE OR REPLACE FUNCTION auth_register_owner(
    p_org_name TEXT,
    p_email TEXT,
    p_password_hash TEXT,
    p_full_name TEXT
)
RETURNS TABLE (org_id UUID, user_id UUID)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_org_id  UUID;
    v_user_id UUID;
BEGIN
    INSERT INTO organizations (name)
    VALUES (p_org_name)
    RETURNING id INTO v_org_id;

    INSERT INTO users (org_id, email, password_hash, full_name, role)
    VALUES (v_org_id, lower(trim(p_email)), p_password_hash, p_full_name, 'owner')
    RETURNING id INTO v_user_id;

    RETURN QUERY SELECT v_org_id, v_user_id;
END $$;

CREATE OR REPLACE FUNCTION auth_get_user_by_email(p_email TEXT)
RETURNS TABLE (id UUID, org_id UUID, password_hash TEXT, full_name TEXT, role user_role)
LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
    SELECT id, org_id, password_hash, full_name, role
    FROM users
    WHERE lower(email) = lower(trim(p_email))
    LIMIT 1;
$$;

-- =====================================================================
-- 11. SEMILLAS: fuentes verificadas y catálogos mínimos
-- =====================================================================
INSERT INTO data_sources (name, url, citation, version) VALUES
 ('NASA POWER', 'https://power.larc.nasa.gov',
  'These data were obtained from the NASA Langley Research Center POWER Project funded through the NASA Earth Science Directorate Applied Science Program.', 'API v2'),
 ('FAO-56 Crop evapotranspiration (Allen et al., 1998)', 'https://www.fao.org/4/X0490e/x0490e0e.htm',
  'Allen, R.G., Pereira, L.S., Raes, D., Smith, M. (1998). FAO Irrigation and Drainage Paper 56. FAO, Rome.', '1998'),
 ('ISRIC SoilGrids', 'https://soilgrids.org',
  'Poggio et al. (2021). SoilGrids 2.0. SOIL 7, 217-240. Licencia CC BY 4.0.', '2.0'),
 ('FAO EcoCrop', 'https://www.fao.org/geospatial/data-and-tools/data-portals/ecocrop/',
  'FAO ECOCROP (1999), accesible vía plataforma GAEZ.', NULL),
 ('Open-Meteo', 'https://open-meteo.com',
  'Open-Meteo, CC BY 4.0. Uso gratuito solo no comercial.', NULL),
 ('Simulador de pH AgroStake', NULL,
  'Valores de pH generados por simulación para la demo del Hacka-NASA 2026. No son mediciones reales.', 'v1');

-- Texturas de suelo (nombres de FAO-56 Tabla 19).
INSERT INTO soil_texture_classes (code, name_es) VALUES
 ('sand','Arena'), ('loamy_sand','Arena franca'), ('sandy_loam','Franco arenoso'),
 ('loam','Franco'), ('silt_loam','Franco limoso'), ('silt','Limo'),
 ('silty_clay_loam','Franco arcillo limoso'), ('silty_clay','Arcillo limoso'), ('clay','Arcilla');

-- Características hídricas por textura precargadas desde FAO-56 Tabla 19 (m3/m3).
INSERT INTO soil_water_characteristics (texture_code, fc_min, fc_max, wp_min, wp_max, source_id)
SELECT t.texture_code, t.fc_min, t.fc_max, t.wp_min, t.wp_max,
       (SELECT id FROM data_sources WHERE name LIKE 'FAO-56%')
FROM (VALUES
    ('sand',            0.070, 0.170, 0.020, 0.070),
    ('loamy_sand',      0.110, 0.190, 0.030, 0.100),
    ('sandy_loam',      0.180, 0.280, 0.060, 0.160),
    ('loam',            0.200, 0.300, 0.070, 0.170),
    ('silt_loam',       0.220, 0.360, 0.090, 0.210),
    ('silt',            0.280, 0.360, 0.120, 0.220),
    ('silty_clay_loam', 0.300, 0.370, 0.170, 0.240),
    ('silty_clay',      0.300, 0.420, 0.170, 0.290),
    ('clay',            0.320, 0.400, 0.200, 0.240)
) AS t(texture_code, fc_min, fc_max, wp_min, wp_max);

-- Consejos de humedad, respaldados por FAO-56 (umbral de riego).
INSERT INTO advice_rules (variable, status, message_es, source_id) VALUES
 ('soil_moisture', 'below',
  'Humedad del suelo baja ({current}%): regar para subir hasta {target}%.',
  (SELECT id FROM data_sources WHERE name LIKE 'FAO-56%')),
 ('soil_moisture', 'above',
  'Humedad del suelo alta ({current}%): suspender el riego y revisar el drenaje hasta bajar a {target}%.',
  (SELECT id FROM data_sources WHERE name LIKE 'FAO-56%'));

-- =====================================================================
-- 12. OPCIONAL: TimescaleDB
-- Nota: si activas TimescaleDB, measured_at debe formar parte de cualquier
-- restricción UNIQUE o PRIMARY KEY en soil_readings.
-- =====================================================================
-- CREATE EXTENSION IF NOT EXISTS timescaledb;
-- ALTER TABLE soil_readings DROP CONSTRAINT soil_readings_pkey,
--   DROP CONSTRAINT soil_readings_stake_id_msg_id_key,
--   ADD PRIMARY KEY (stake_id, measured_at),
--   ADD UNIQUE (stake_id, msg_id, measured_at);
-- SELECT create_hypertable('soil_readings', 'measured_at', chunk_time_interval => INTERVAL '7 days');


-- #####################################################################
-- ########################  AGROSTAKE v3.3  ###########################
-- ##  Todo lo que sigue se agrega sobre el esquema v3.2 de arriba.   ##
-- #####################################################################

-- =====================================================================
-- 13. MÓDULO IA & PROYECCIÓN TEMPORAL (AgenteIA.txt) + validaciones
-- =====================================================================
ALTER TABLE crops
    ADD COLUMN IF NOT EXISTS cycle_days_min INTEGER DEFAULT 90,
    ADD COLUMN IF NOT EXISTS cycle_days_max INTEGER DEFAULT 120,
    ADD COLUMN IF NOT EXISTS harvest_notes  TEXT;

ALTER TABLE crops
    ADD CONSTRAINT crops_cycle_days_chk
    CHECK (cycle_days_min IS NULL OR cycle_days_max IS NULL
           OR (cycle_days_min > 0 AND cycle_days_min <= cycle_days_max));

ALTER TABLE recommendation_results
    ADD COLUMN IF NOT EXISTS ml_suitability_score NUMERIC(5,2),  -- probabilidad 0-100 (XGBoost)
    ADD COLUMN IF NOT EXISTS projected_days       INTEGER,       -- horizonte evaluado (ej. 110 días)
    ADD COLUMN IF NOT EXISTS future_risk_summary  TEXT;          -- resumen climático a futuro

ALTER TABLE recommendation_results
    ADD CONSTRAINT rec_results_ml_score_chk
        CHECK (ml_suitability_score IS NULL OR ml_suitability_score BETWEEN 0 AND 100),
    ADD CONSTRAINT rec_results_projected_days_chk
        CHECK (projected_days IS NULL OR projected_days > 0);

-- =====================================================================
-- 14. parcel_crops (guía de acoplamiento 1.1): cultivo(s) de cada parcela
-- =====================================================================
CREATE TABLE parcel_crops (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parcel_id   UUID NOT NULL REFERENCES parcels(id) ON DELETE CASCADE,
    crop_id     INTEGER NOT NULL REFERENCES crops(id),
    status      TEXT NOT NULL DEFAULT 'planificado'
                CHECK (status IN ('planificado', 'activo', 'cosechado')),
    sown_at     DATE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (parcel_id, crop_id, status)
);
CREATE INDEX idx_parcel_crops_parcel ON parcel_crops(parcel_id);
CREATE INDEX idx_parcel_crops_crop   ON parcel_crops(crop_id);

ALTER TABLE parcel_crops ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_parcel_crops ON parcel_crops
    FOR ALL
    USING (EXISTS (SELECT 1 FROM parcels p WHERE p.id = parcel_id))
    WITH CHECK (EXISTS (SELECT 1 FROM parcels p WHERE p.id = parcel_id));

-- =====================================================================
-- 15. ALERTAS TAMBIÉN POR PARCELA (guía 1.2)
-- Permite alertas climáticas para parcelas sin estaca física vinculada.
-- Toda alerta debe apuntar a una estaca, a una parcela o a ambas.
-- =====================================================================
ALTER TABLE alerts ALTER COLUMN stake_id DROP NOT NULL;
ALTER TABLE alerts ADD COLUMN parcel_id UUID REFERENCES parcels(id) ON DELETE CASCADE;
ALTER TABLE alerts ADD CONSTRAINT alerts_target_chk
    CHECK (stake_id IS NOT NULL OR parcel_id IS NOT NULL);

ALTER TABLE alerts DROP CONSTRAINT alerts_kind_check;
ALTER TABLE alerts ADD CONSTRAINT alerts_kind_check
    CHECK (kind IN ('bateria_baja','sin_reporte','lectura_fuera_de_rango','humedad_baja','clima_adverso'));

CREATE INDEX idx_alerts_open_parcel ON alerts(parcel_id)
    WHERE resolved_at IS NULL AND parcel_id IS NOT NULL;

DROP POLICY tenant_alerts ON alerts;
CREATE POLICY tenant_alerts ON alerts
    FOR ALL
    USING (   (stake_id  IS NOT NULL AND EXISTS (SELECT 1 FROM stakes  s WHERE s.id = stake_id))
           OR (parcel_id IS NOT NULL AND EXISTS (SELECT 1 FROM parcels p WHERE p.id = parcel_id)))
    WITH CHECK (   (stake_id  IS NOT NULL AND EXISTS (SELECT 1 FROM stakes  s WHERE s.id = stake_id))
                OR (parcel_id IS NOT NULL AND EXISTS (SELECT 1 FROM parcels p WHERE p.id = parcel_id)));

-- =====================================================================
-- 16. rainfall_window: origin alineado con el contrato JSON ('nasa_power')
-- El producto concreto (merra2_prectotcorr) pasa a la columna precip_product.
-- Si la cobertura es menor a p_min_coverage, precip_total_mm = NULL y el
-- motor debe marcar la variable como not_evaluated (nunca 0).
-- =====================================================================
DROP FUNCTION rainfall_window(UUID, DATE, INT, NUMERIC);
CREATE FUNCTION rainfall_window(
    p_parcel UUID, p_end DATE, p_days INT DEFAULT 30, p_min_coverage NUMERIC DEFAULT 0.8)
RETURNS TABLE (precip_total_mm NUMERIC, origin TEXT, precip_product TEXT,
               days_with_data INT, window_days INT, last_valid_date DATE)
LANGUAGE sql STABLE AS $$
    SELECT CASE WHEN count(w.precip_mm) >= ceil(p_days * p_min_coverage)
                THEN round(sum(w.precip_mm), 2) END,
           CASE WHEN count(w.precip_mm) > 0 THEN 'nasa_power' ELSE 'sin_datos' END,
           max(w.precip_product),
           count(w.precip_mm)::int,
           p_days,
           max(w.obs_date) FILTER (WHERE w.precip_mm IS NOT NULL)
    FROM parcels p
    JOIN climate_cells c ON c.id = p.climate_cell_id AND c.source = 'nasa_power'
    LEFT JOIN weather_daily w
           ON w.cell_id = c.id
          AND w.obs_date >  p_end - p_days
          AND w.obs_date <= p_end
    WHERE p.id = p_parcel;
$$;

-- =====================================================================
-- 17. EXIGIR LAS 4 VARIABLES POR CULTIVO EVALUADO (guía 4.1, regla 1)
-- Trigger diferido: al confirmar la transacción, cada recommendation_results
-- debe tener exactamente soil_temperature, soil_moisture, soil_ph y rainfall.
-- (La PK y el FK a viability_rule_variables garantizan que no se repitan ni
--  sean otras; aquí solo se verifica que estén las 4.)
-- =====================================================================
CREATE FUNCTION check_four_variables() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_run  UUID;
    v_crop INTEGER;
    v_n    INT;
BEGIN
    IF TG_OP = 'DELETE' THEN
        v_run := OLD.run_id;  v_crop := OLD.crop_id;
    ELSE
        v_run := NEW.run_id;  v_crop := NEW.crop_id;
    END IF;

    -- Si el resultado ya no existe (borrado en cascada), no hay nada que validar.
    IF NOT EXISTS (SELECT 1 FROM recommendation_results
                   WHERE run_id = v_run AND crop_id = v_crop) THEN
        RETURN NULL;
    END IF;

    SELECT count(DISTINCT variable) INTO v_n
    FROM recommendation_checks
    WHERE run_id = v_run AND crop_id = v_crop;

    IF v_n <> 4 THEN
        RAISE EXCEPTION 'Cada cultivo evaluado debe tener las 4 variables (tiene %): run % cultivo %',
            v_n, v_run, v_crop;
    END IF;
    RETURN NULL;
END $$;

CREATE CONSTRAINT TRIGGER trg_results_four_vars
    AFTER INSERT OR UPDATE ON recommendation_results
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION check_four_variables();

CREATE CONSTRAINT TRIGGER trg_checks_four_vars
    AFTER INSERT OR UPDATE OR DELETE ON recommendation_checks
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION check_four_variables();

-- =====================================================================
-- 18. SEMILLAS: consejos (advice_rules) para temperatura, pH y lluvia
-- (v3.2 solo traía humedad). Admiten {current} y {target}.
-- =====================================================================
INSERT INTO advice_rules (variable, status, message_es, source_id) VALUES
 ('soil_temperature','below',
  'Temperatura del suelo baja ({current} °C): conviene retrasar la siembra o usar acolchado para acercarse a {target} °C.',
  (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')),
 ('soil_temperature','above',
  'Temperatura del suelo alta ({current} °C): conviene usar acolchado y riegos ligeros para bajar hacia {target} °C.',
  (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')),
 ('soil_ph','below',
  'pH del suelo bajo, suelo ácido ({current}): considerar encalado agrícola para subir hacia {target}.',
  (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')),
 ('soil_ph','above',
  'pH del suelo alto, suelo alcalino ({current}): considerar materia orgánica o azufre elemental para bajar hacia {target}.',
  (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')),
 ('rainfall','below',
  'Lluvia acumulada baja ({current} mm): programar riego complementario para aproximarse a {target} mm.',
  (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')),
 ('rainfall','above',
  'Lluvia acumulada alta ({current} mm): vigilar encharcamiento y mejorar el drenaje; el objetivo es cerca de {target} mm.',
  (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop'))
ON CONFLICT (variable, status) DO NOTHING;

-- =====================================================================
-- 19. FORCE ROW LEVEL SECURITY en las 16 tablas multi-tenant
-- (el dueño de las tablas también queda sujeto a las políticas)
-- =====================================================================
ALTER TABLE organizations          FORCE ROW LEVEL SECURITY;
ALTER TABLE users                  FORCE ROW LEVEL SECURITY;
ALTER TABLE refresh_tokens         FORCE ROW LEVEL SECURITY;
ALTER TABLE sync_clients           FORCE ROW LEVEL SECURITY;
ALTER TABLE parcels                FORCE ROW LEVEL SECURITY;
ALTER TABLE stakes                 FORCE ROW LEVEL SECURITY;
ALTER TABLE sensor_calibrations    FORCE ROW LEVEL SECURITY;
ALTER TABLE soil_readings          FORCE ROW LEVEL SECURITY;
ALTER TABLE alerts                 FORCE ROW LEVEL SECURITY;
ALTER TABLE soil_ph_observations   FORCE ROW LEVEL SECURITY;
ALTER TABLE soil_samples           FORCE ROW LEVEL SECURITY;
ALTER TABLE soil_sample_values     FORCE ROW LEVEL SECURITY;
ALTER TABLE recommendation_runs    FORCE ROW LEVEL SECURITY;
ALTER TABLE recommendation_results FORCE ROW LEVEL SECURITY;
ALTER TABLE recommendation_checks  FORCE ROW LEVEL SECURITY;
ALTER TABLE parcel_crops           FORCE ROW LEVEL SECURITY;

-- =====================================================================
-- 20. FUNCIONES SECURITY DEFINER (complementos) Y PERMISOS MÍNIMOS
-- =====================================================================
CREATE OR REPLACE FUNCTION auth_lookup_refresh_token(p_token_hash TEXT)
RETURNS TABLE (token_id UUID, user_id UUID, org_id UUID, role user_role,
               expires_at TIMESTAMPTZ, revoked_at TIMESTAMPTZ)
LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
    SELECT rt.id, u.id, u.org_id, u.role, rt.expires_at, rt.revoked_at
    FROM refresh_tokens rt
    JOIN users u ON u.id = rt.user_id
    WHERE rt.token_hash = p_token_hash
    LIMIT 1;
$$;

CREATE OR REPLACE FUNCTION iot_resolve_stake_context(p_device_uid TEXT)
RETURNS TABLE (stake_id UUID, org_id UUID, parcel_id UUID, is_active BOOLEAN)
LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
    SELECT id, org_id, parcel_id, is_active
    FROM stakes
    WHERE device_uid = trim(p_device_uid)
    LIMIT 1;
$$;

-- ---- 20.1 Rol definer: dueño de las 4 funciones SECURITY DEFINER ------
-- Privilegios mínimos que esas funciones necesitan (BYPASSRLS ya salta RLS).
GRANT USAGE ON SCHEMA public TO agrostake_definer;
GRANT SELECT, INSERT ON organizations, users TO agrostake_definer;
GRANT SELECT         ON refresh_tokens, stakes TO agrostake_definer;

-- ALTER ... OWNER exige que el nuevo dueño tenga CREATE en el esquema:
-- se concede solo durante el cambio y se retira enseguida.
GRANT CREATE ON SCHEMA public TO agrostake_definer;
ALTER FUNCTION auth_register_owner(TEXT, TEXT, TEXT, TEXT) OWNER TO agrostake_definer;
ALTER FUNCTION auth_get_user_by_email(TEXT)                OWNER TO agrostake_definer;
ALTER FUNCTION auth_lookup_refresh_token(TEXT)             OWNER TO agrostake_definer;
ALTER FUNCTION iot_resolve_stake_context(TEXT)             OWNER TO agrostake_definer;
REVOKE CREATE ON SCHEMA public FROM agrostake_definer;

-- ---- 20.2 Permisos del backend (agrostake_app) ------------------------
REVOKE ALL ON ALL TABLES    IN SCHEMA public FROM agrostake_app;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM agrostake_app;
GRANT USAGE ON SCHEMA public TO agrostake_app;

-- Tablas multi-tenant: lectura y escritura (RLS acota cada organización).
GRANT SELECT, INSERT, UPDATE, DELETE ON
    organizations, users, refresh_tokens, sync_clients,
    parcels, stakes, sensor_calibrations, soil_readings, alerts,
    soil_ph_observations, soil_samples, soil_sample_values,
    recommendation_runs, recommendation_results, recommendation_checks,
    parcel_crops
TO agrostake_app;

-- Clima global (Backend 2 hace UPSERT diario de NASA POWER). Sin DELETE.
GRANT SELECT, INSERT, UPDATE ON climate_cells, weather_daily TO agrostake_app;

-- Catálogos de referencia: SOLO LECTURA para la app.
-- Se modifican únicamente con agrostake_owner (migraciones / semillas).
GRANT SELECT ON
    data_sources, crops, crop_requirements, viability_rule_variables,
    soil_elements, crop_element_requirements, soil_texture_classes,
    soil_water_characteristics, crop_irrigation_params, advice_rules
TO agrostake_app;

GRANT SELECT ON v_crop_moisture_range, latest_soil_ph TO agrostake_app;

-- Funciones SECURITY DEFINER: solo la app puede ejecutarlas.
REVOKE EXECUTE ON FUNCTION
    auth_register_owner(TEXT, TEXT, TEXT, TEXT),
    auth_get_user_by_email(TEXT),
    auth_lookup_refresh_token(TEXT),
    iot_resolve_stake_context(TEXT)
FROM PUBLIC;
GRANT EXECUTE ON FUNCTION
    auth_register_owner(TEXT, TEXT, TEXT, TEXT),
    auth_get_user_by_email(TEXT),
    auth_lookup_refresh_token(TEXT),
    iot_resolve_stake_context(TEXT)
TO agrostake_app;

-- Funciones de apoyo (INVOKER): la app las ejecuta bajo su propio RLS.
GRANT EXECUTE ON FUNCTION
    app_org_id(),
    nasa_grid_center(NUMERIC, NUMERIC),
    soil_window(UUID, DATE, INT, BOOLEAN),
    latest_weather_date(UUID),
    rainfall_window(UUID, DATE, INT, NUMERIC)
TO agrostake_app;

-- =====================================================================
-- 21. PARCHE v3.3.1 (pedido por el equipo)
-- 21.1 recommendation_checks.origin debe aceptar 'dataset_estimado':
--      ph_method ya lo permite y sin esto se rechazarían esas evaluaciones.
-- 21.2 Evitar alertas ABIERTAS duplicadas ante paquetes simultáneos de la
--      misma estaca o parcela. Los backends deben insertar con:
--        INSERT INTO alerts (...) VALUES (...)
--        ON CONFLICT (stake_id, kind)
--          WHERE resolved_at IS NULL AND stake_id IS NOT NULL DO NOTHING;
--      (y, para alertas solo de parcela:
--        ON CONFLICT (parcel_id, kind)
--          WHERE resolved_at IS NULL AND parcel_id IS NOT NULL AND stake_id IS NULL DO NOTHING;)
-- =====================================================================
ALTER TABLE recommendation_checks
    DROP CONSTRAINT IF EXISTS recommendation_checks_origin_check;

ALTER TABLE recommendation_checks
    ADD CONSTRAINT recommendation_checks_origin_check
    CHECK (origin IN ('estaca', 'nasa_power', 'simulado', 'manual', 'laboratorio', 'dataset_estimado'));

CREATE UNIQUE INDEX IF NOT EXISTS uq_alerts_open_stake_kind
    ON alerts (stake_id, kind)
    WHERE resolved_at IS NULL AND stake_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_alerts_open_parcel_kind
    ON alerts (parcel_id, kind)
    WHERE resolved_at IS NULL AND parcel_id IS NOT NULL AND stake_id IS NULL;

-- =====================================================================
-- FIN · AgroStake v3.3
-- Siguiente: (opcional) 02_seed_demo_cultivos.sql  y  03_verificacion.sql
-- =====================================================================


-- #####################################################################
-- PARTE 3 · SEMILLAS DEMO DE CULTIVOS (valores aproximados, ver aviso)
-- #####################################################################
-- =====================================================================
-- AgroStake v3.3 · SEMILLAS DEMO de cultivos (OPCIONAL)
-- Ejecutar como agrostake_owner DESPUÉS de 01_agrostake_schema_v3_3.sql:
--
--   psql -U agrostake_owner -d agrostake -v ON_ERROR_STOP=1 -f 02_seed_demo_cultivos.sql
--
-- ATENCIÓN: son valores APROXIMADOS para que el equipo pueda probar el
-- motor de recomendación de punta a punta. NO son datos validados por un
-- agrónomo. Están registrados bajo la fuente 'Valores demo AgroStake'
-- (nunca como si vinieran de FAO/EcoCrop) y deben reemplazarse por los
-- rangos reales (p05-p95 de Dataset_Crop.csv / EcoCrop) antes de usar el
-- sistema con productores.
--
--   * Fracción de agotamiento p y profundidad radicular: orden de magnitud
--     de FAO-56 Tabla 22 (fuente FAO-56).
--   * Temperatura del suelo, pH y lluvia a 30 días: rangos demo aproximados.
--   * La humedad NO se siembra: la calcula v_crop_moisture_range (FAO-56)
--     a partir de crop_irrigation_params + soil_water_characteristics.
-- =====================================================================

INSERT INTO data_sources (name, url, citation, version)
VALUES ('Valores demo AgroStake', NULL,
        'Rangos aproximados para demo de Hacka-NASA 2026. No validados por un agrónomo; reemplazar por datos de dataset/EcoCrop.',
        'demo-1')
ON CONFLICT (name) DO NOTHING;

-- ---- Cultivos ---------------------------------------------------------
INSERT INTO crops (common_name_es, scientific_name, dataset_label, category,
                   source_id, cycle_days_min, cycle_days_max, harvest_notes)
SELECT v.common_name_es, v.scientific_name, v.dataset_label, v.category,
       (SELECT id FROM data_sources WHERE name = 'Valores demo AgroStake'),
       v.cmin, v.cmax, v.notes
FROM (VALUES
  ('Maíz',   'Zea mays',            'maize',       'cereal',     100, 140, 'Cosecha con grano en madurez fisiológica.'),
  ('Frijol', 'Phaseolus vulgaris',  'kidneybeans', 'leguminosa',  70, 110, 'Cosechar con vainas secas.'),
  ('Arroz',  'Oryza sativa',        'rice',        'cereal',    105, 150, 'Requiere lámina de agua; sensible a sequía.'),
  ('Trigo',  'Triticum aestivum',   NULL,          'cereal',    110, 150, 'Cultivo de clima templado/frío.'),
  ('Sorgo',  'Sorghum bicolor',     NULL,          'cereal',    100, 130, 'Tolerante a sequía.'),
  ('Tomate', 'Solanum lycopersicum',NULL,          'hortaliza',  90, 140, 'Cosecha escalonada.')
) AS v(common_name_es, scientific_name, dataset_label, category, cmin, cmax, notes)
ON CONFLICT (scientific_name) DO NOTHING;

-- ---- Rangos por variable (temperatura del suelo °C, pH, lluvia mm/30 d) --
INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT c.id, r.variable::variable_code, r.omin, r.omax, r.unit,
       'valor demo aproximado; validar',
       (SELECT id FROM data_sources WHERE name = 'Valores demo AgroStake')
FROM crops c
JOIN (VALUES
  ('Maíz',   'soil_temperature', 18.0,  30.0, '°C'),
  ('Maíz',   'soil_ph',           5.8,   7.0, 'pH'),
  ('Maíz',   'rainfall',         50.0, 120.0, 'mm'),
  ('Frijol', 'soil_temperature', 15.0,  27.0, '°C'),
  ('Frijol', 'soil_ph',           6.0,   7.0, 'pH'),
  ('Frijol', 'rainfall',         40.0, 100.0, 'mm'),
  ('Arroz',  'soil_temperature', 20.0,  32.0, '°C'),
  ('Arroz',  'soil_ph',           5.5,   7.0, 'pH'),
  ('Arroz',  'rainfall',        120.0, 300.0, 'mm'),
  ('Trigo',  'soil_temperature', 10.0,  24.0, '°C'),
  ('Trigo',  'soil_ph',           6.0,   7.5, 'pH'),
  ('Trigo',  'rainfall',         40.0,  90.0, 'mm'),
  ('Sorgo',  'soil_temperature', 20.0,  32.0, '°C'),
  ('Sorgo',  'soil_ph',           5.5,   7.5, 'pH'),
  ('Sorgo',  'rainfall',         40.0, 100.0, 'mm'),
  ('Tomate', 'soil_temperature', 18.0,  28.0, '°C'),
  ('Tomate', 'soil_ph',           6.0,   6.8, 'pH'),
  ('Tomate', 'rainfall',         50.0, 110.0, 'mm')
) AS r(nombre, variable, omin, omax, unit) ON r.nombre = c.common_name_es
ON CONFLICT (crop_id, variable) DO NOTHING;

-- ---- Parámetros de riego FAO-56 (Tabla 22, orden de magnitud) -----------
INSERT INTO crop_irrigation_params (crop_id, root_depth_m_min, root_depth_m_max,
                                    depletion_fraction_p, source_id)
SELECT c.id, p.rmin, p.rmax, p.p,
       (SELECT id FROM data_sources WHERE name LIKE 'FAO-56%')
FROM crops c
JOIN (VALUES
  ('Maíz',   1.00, 1.70, 0.55),
  ('Frijol', 0.50, 0.70, 0.45),
  ('Arroz',  0.50, 1.00, 0.20),
  ('Trigo',  1.50, 1.80, 0.55),
  ('Sorgo',  1.00, 2.00, 0.55),
  ('Tomate', 0.70, 1.50, 0.40)
) AS p(nombre, rmin, rmax, p) ON p.nombre = c.common_name_es
ON CONFLICT (crop_id) DO NOTHING;

\echo 'Semillas demo cargadas: 6 cultivos con rangos y parámetros de riego.'


-- #####################################################################
-- PARTE 4 · VERIFICACIÓN AUTOMÁTICA (como superusuario; termina en ROLLBACK)
-- #####################################################################
RESET SESSION AUTHORIZATION;
-- =====================================================================
-- AgroStake v3.3 · VERIFICACIÓN AUTOMÁTICA
-- Ejecutar como SUPERUSUARIO (necesita SET ROLE) sobre la base ya cargada:
--
--   psql -U postgres -d agrostake -v ON_ERROR_STOP=1 -f 03_verificacion.sql
--
-- Todo corre dentro de una transacción que termina en ROLLBACK: no deja
-- datos de prueba. Si algo falla, el script se detiene con "TFALLO: ...".
-- Si todo sale bien, la última línea dice: TODAS LAS PRUEBAS OK.
-- Las pruebas se ejecutan como agrostake_app (el rol real de los backends),
-- así que validan RLS, permisos y funciones tal como los verán tus compañeros.
-- =====================================================================
BEGIN;

DO $$
DECLARE
    v_org_a UUID; v_user_a UUID; v_org_b UUID; v_user_b UUID;
    v_cell UUID; v_parcel UUID; v_stake UUID;
    v_crop INT; v_crop2 INT; v_run UUID;
    v_n INT; v_num NUMERIC; v_txt TEXT; v_date DATE; v_advice INT;
    v_super BOOLEAN; v_bypass BOOLEAN;
    v_stmt TEXT;
BEGIN
    -- ------------------------------------------------------------
    -- Preparación (como superusuario): cultivos de prueba
    -- ------------------------------------------------------------
    INSERT INTO crops (common_name_es, scientific_name, cycle_days_min, cycle_days_max)
    VALUES ('__prueba_1__', '__prueba_1__', 90, 120) RETURNING id INTO v_crop;
    INSERT INTO crops (common_name_es, scientific_name, cycle_days_min, cycle_days_max)
    VALUES ('__prueba_2__', '__prueba_2__', 90, 120) RETURNING id INTO v_crop2;
    INSERT INTO crop_irrigation_params (crop_id, depletion_fraction_p) VALUES (v_crop, 0.55);

    SELECT id INTO v_advice FROM advice_rules WHERE variable = 'soil_moisture' AND status = 'below';

    -- A partir de aquí TODO corre como el rol real de la aplicación
    SET LOCAL ROLE agrostake_app;

    SELECT rolsuper, rolbypassrls INTO v_super, v_bypass FROM pg_roles WHERE rolname = 'agrostake_app';
    IF v_super OR v_bypass THEN
        RAISE EXCEPTION USING ERRCODE = 'AS999', MESSAGE = 'TFALLO T0: agrostake_app no debe ser superusuario ni BYPASSRLS';
    END IF;
    RAISE NOTICE 'OK T0  rol de la app sin superusuario ni BYPASSRLS';

    -- ------------------------------------------------------------
    -- T1: funciones SECURITY DEFINER (registro, login, refresh, IoT)
    -- ------------------------------------------------------------
    SELECT r.org_id, r.user_id INTO v_org_a, v_user_a FROM auth_register_owner('Org A', 'a@test.local', 'hash', 'Ana') r;
    SELECT r.org_id, r.user_id INTO v_org_b, v_user_b FROM auth_register_owner('Org B', 'b@test.local', 'hash', 'Beto') r;
    IF v_org_a IS NULL OR v_org_b IS NULL THEN
        RAISE EXCEPTION USING ERRCODE = 'AS999', MESSAGE = 'TFALLO T1a: auth_register_owner no devolvió org';
    END IF;

    SELECT count(*) INTO v_n FROM auth_get_user_by_email('  A@TEST.local ') g WHERE g.id = v_user_a AND g.role = 'owner';
    IF v_n <> 1 THEN
        RAISE EXCEPTION USING ERRCODE = 'AS999', MESSAGE = 'TFALLO T1b: auth_get_user_by_email no encontró al usuario';
    END IF;

    PERFORM set_config('app.org_id', v_org_a::text, true);
    INSERT INTO refresh_tokens (user_id, token_hash, expires_at) VALUES (v_user_a, 'tokhash', now() + interval '1 day');
    PERFORM set_config('app.org_id', '', true);          -- sin tenant, como antes de autenticar
    SELECT count(*) INTO v_n FROM auth_lookup_refresh_token('tokhash') t WHERE t.org_id = v_org_a;
    IF v_n <> 1 THEN
        RAISE EXCEPTION USING ERRCODE = 'AS999', MESSAGE = 'TFALLO T1c: auth_lookup_refresh_token no resolvió el token';
    END IF;
    RAISE NOTICE 'OK T1  registro, login y refresh token funcionan con FORCE RLS';

    -- Datos de la Org A
    PERFORM set_config('app.org_id', v_org_a::text, true);
    INSERT INTO climate_cells (source, center_lat, center_lon)
    SELECT 'nasa_power', center_lat, center_lon FROM nasa_grid_center(25.42, -101.0)
    RETURNING id INTO v_cell;
    INSERT INTO parcels (org_id, name, latitude, longitude, soil_texture, climate_cell_id)
    VALUES (v_org_a, 'Parcela A', 25.42, -101.0, 'loam', v_cell) RETURNING id INTO v_parcel;
    INSERT INTO stakes (org_id, parcel_id, device_uid) VALUES (v_org_a, v_parcel, 'ESP-TEST-1') RETURNING id INTO v_stake;

    PERFORM set_config('app.org_id', '', true);
    SELECT count(*) INTO v_n FROM iot_resolve_stake_context(' ESP-TEST-1 ') s
    WHERE s.org_id = v_org_a AND s.parcel_id = v_parcel AND s.stake_id = v_stake AND s.is_active;
    IF v_n <> 1 THEN
        RAISE EXCEPTION USING ERRCODE = 'AS999', MESSAGE = 'TFALLO T1d: iot_resolve_stake_context no resolvió la estaca';
    END IF;
    RAISE NOTICE 'OK T1b resolución de contexto de estaca IoT (sin tenant) funciona';

    -- ------------------------------------------------------------
    -- T2: aislamiento entre organizaciones (RLS)
    -- ------------------------------------------------------------
    PERFORM set_config('app.org_id', v_org_b::text, true);
    SELECT (SELECT count(*) FROM parcels) + (SELECT count(*) FROM stakes) + (SELECT count(*) FROM users WHERE org_id = v_org_a)
      INTO v_n;
    IF v_n <> 0 THEN
        RAISE EXCEPTION USING ERRCODE = 'AS999', MESSAGE = 'TFALLO T2a: la Org B ve datos de la Org A';
    END IF;

    BEGIN
        INSERT INTO soil_readings (stake_id, measured_at, msg_id, transport, soil_temperature_c)
        VALUES (v_stake, now(), 'x1', 'ble', 20);
        RAISE EXCEPTION USING ERRCODE = 'AS999', MESSAGE = 'TFALLO T2b: la Org B pudo insertar lecturas en una estaca ajena';
    EXCEPTION WHEN insufficient_privilege THEN NULL; END;

    BEGIN
        INSERT INTO parcel_crops (parcel_id, crop_id) VALUES (v_parcel, v_crop);
        RAISE EXCEPTION USING ERRCODE = 'AS999', MESSAGE = 'TFALLO T2c: la Org B pudo crear parcel_crops en una parcela ajena';
    EXCEPTION WHEN insufficient_privilege THEN NULL; END;

    BEGIN
        INSERT INTO alerts (parcel_id, kind, severity) VALUES (v_parcel, 'clima_adverso', 'aviso');
        RAISE EXCEPTION USING ERRCODE = 'AS999', MESSAGE = 'TFALLO T2d: la Org B pudo crear alertas en una parcela ajena';
    EXCEPTION WHEN insufficient_privilege THEN NULL; END;
    RAISE NOTICE 'OK T2  aislamiento multi-tenant (lectura y escritura cruzada bloqueadas)';

    -- ------------------------------------------------------------
    -- T3: catálogos globales protegidos (solo lectura para la app)
    -- ------------------------------------------------------------
    FOREACH v_stmt IN ARRAY ARRAY[
        'DELETE FROM advice_rules',
        'UPDATE data_sources SET citation = ''x''',
        'INSERT INTO crops (common_name_es) VALUES (''hack'')',
        'UPDATE crop_requirements SET optimal_min = 0',
        'DELETE FROM soil_water_characteristics'
    ] LOOP
        BEGIN
            EXECUTE v_stmt;
            RAISE EXCEPTION USING ERRCODE = 'AS999', MESSAGE = 'TFALLO T3: la app pudo ejecutar: ' || v_stmt;
        EXCEPTION WHEN insufficient_privilege THEN NULL; END;
    END LOOP;
    SELECT count(*) INTO v_n FROM advice_rules;
    IF v_n < 8 THEN
        RAISE EXCEPTION USING ERRCODE = 'AS999', MESSAGE = 'TFALLO T3b: faltan advice_rules (hay ' || v_n || ', se esperan >= 8)';
    END IF;
    RAISE NOTICE 'OK T3  catálogos de solo lectura; advice_rules sembradas (%)', v_n;

    -- ------------------------------------------------------------
    -- T4: clima NASA POWER (-999 -> NULL, UPSERT, ventanas)
    -- ------------------------------------------------------------
    BEGIN
        INSERT INTO weather_daily (cell_id, obs_date, precip_mm) VALUES (v_cell, '2026-11-01', -999);
        RAISE EXCEPTION USING ERRCODE = 'AS999', MESSAGE = 'TFALLO T4a: se aceptó precip = -999';
    EXCEPTION WHEN check_violation THEN NULL; END;

    INSERT INTO weather_daily (cell_id, obs_date, precip_mm)
    SELECT v_cell, d::date, 2.5 FROM generate_series('2026-10-14'::date, '2026-11-10'::date, '1 day') d;
    INSERT INTO weather_daily (cell_id, obs_date, precip_mm) VALUES (v_cell, '2026-11-11', NULL), (v_cell, '2026-11-12', NULL);

    PERFORM set_config('app.org_id', v_org_a::text, true);
    SELECT precip_total_mm, origin INTO v_num, v_txt FROM rainfall_window(v_parcel, '2026-11-12', 30);
    IF v_num IS DISTINCT FROM 70.00 OR v_txt <> 'nasa_power' THEN
        RAISE EXCEPTION USING ERRCODE = 'AS999', MESSAGE = format('TFALLO T4b: rainfall_window dio total=%s origin=%s (esperado 70.00 / nasa_power)', v_num, v_txt);
    END IF;

    SELECT precip_total_mm INTO v_num FROM rainfall_window(v_parcel, '2026-11-12', 60);   -- 28/60 < 80 %
    IF v_num IS NOT NULL THEN
        RAISE EXCEPTION USING ERRCODE = 'AS999', MESSAGE = 'TFALLO T4c: con cobertura < 80 % debe devolver NULL (not_evaluated), no un número';
    END IF;

    INSERT INTO weather_daily (cell_id, obs_date, precip_mm) VALUES (v_cell, '2026-11-11', 3.0)
    ON CONFLICT (cell_id, obs_date) DO UPDATE SET precip_mm = EXCLUDED.precip_mm, fetched_at = now();
    SELECT latest_weather_date(v_cell) INTO v_date;
    SELECT precip_total_mm INTO v_num FROM rainfall_window(v_parcel, '2026-11-12', 30);
    IF v_date <> '2026-11-11' OR v_num IS DISTINCT FROM 73.00 THEN
        RAISE EXCEPTION USING ERRCODE = 'AS999', MESSAGE = format('TFALLO T4d: UPSERT/ventana incorrectos (fecha=%s total=%s)', v_date, v_num);
    END IF;

    SELECT count(*) INTO v_n FROM nasa_grid_center(25.42, -101.0) g WHERE g.center_lat = 25.5 AND g.center_lon = -101.250;
    IF v_n <> 1 THEN
        RAISE EXCEPTION USING ERRCODE = 'AS999', MESSAGE = 'TFALLO T4e: nasa_grid_center(25.42,-101.0) debe dar 25.5 / -101.25';
    END IF;
    RAISE NOTICE 'OK T4  -999 rechazado, UPSERT, cobertura 80 %% , origin nasa_power y celda MERRA-2';

    -- ------------------------------------------------------------
    -- T5: telemetría de estaca (NULL en fallo, idempotencia, simulados)
    -- ------------------------------------------------------------
    INSERT INTO soil_readings (stake_id, measured_at, msg_id, transport, soil_temperature_c, soil_moisture_pct) VALUES
        (v_stake, '2026-11-12 10:00+00', 'a', 'ble', 20,   10),
        (v_stake, '2026-11-12 11:00+00', 'b', 'ble', 22,   NULL),     -- humedad falló: NULL, nunca 0
        (v_stake, '2026-11-12 12:00+00', 'c', 'ble', NULL, 14);       -- temperatura falló
    INSERT INTO soil_readings (stake_id, measured_at, msg_id, transport, soil_temperature_c, soil_moisture_pct, is_simulated)
    VALUES (v_stake, '2026-11-12 13:00+00', 'sim', 'ble', 99, 99, true);
    INSERT INTO soil_readings (stake_id, measured_at, msg_id, transport, soil_temperature_c)
    VALUES (v_stake, now(), 'a', 'ble', 1) ON CONFLICT (stake_id, msg_id) DO NOTHING;   -- reenvío

    SELECT count(*) INTO v_n FROM soil_readings WHERE stake_id = v_stake;
    IF v_n <> 4 THEN
        RAISE EXCEPTION USING ERRCODE = 'AS999', MESSAGE = 'TFALLO T5a: la idempotencia (stake_id, msg_id) falló, filas=' || v_n;
    END IF;
    SELECT soil_temp_avg, soil_moisture_avg INTO v_num, v_txt FROM soil_window(v_parcel, '2026-11-12', 7);
    IF v_num IS DISTINCT FROM 21.00 OR v_txt::numeric IS DISTINCT FROM 12.00 THEN
        RAISE EXCEPTION USING ERRCODE = 'AS999', MESSAGE = format('TFALLO T5b: soil_window dio temp=%s hum=%s (esperado 21.00 / 12.00)', v_num, v_txt);
    END IF;

    UPDATE stakes SET last_seen_at = GREATEST(COALESCE(last_seen_at, '2026-11-12 12:00+00'), '2026-11-12 12:00+00'),
                      last_transport = 'ble' WHERE id = v_stake;
    SELECT count(*) INTO v_n FROM stakes WHERE id = v_stake AND last_seen_at IS NOT NULL;
    IF v_n <> 1 THEN
        RAISE EXCEPTION USING ERRCODE = 'AS999', MESSAGE = 'TFALLO T5c: no se actualizó stakes.last_seen_at';
    END IF;
    RAISE NOTICE 'OK T5  telemetría: NULL por sensor fallido, idempotencia, simulados excluidos, last_seen_at';

    -- ------------------------------------------------------------
    -- T6: pH simulado y vista de humedad FAO-56
    -- ------------------------------------------------------------
    INSERT INTO soil_ph_observations (parcel_id, ph, method, source_id)
    VALUES (v_parcel, 6.4, 'simulado', (SELECT id FROM data_sources WHERE name = 'Simulador de pH AgroStake'));
    SELECT ph INTO v_num FROM latest_soil_ph WHERE parcel_id = v_parcel;
    IF v_num IS DISTINCT FROM 6.40 THEN
        RAISE EXCEPTION USING ERRCODE = 'AS999', MESSAGE = 'TFALLO T6a: latest_soil_ph no devolvió 6.4';
    END IF;

    SELECT count(*) INTO v_n FROM v_crop_moisture_range
    WHERE crop_id = v_crop AND texture_code = 'loam' AND optimal_min_pct = 17.9 AND optimal_max_pct = 25.0;
    IF v_n <> 1 THEN
        RAISE EXCEPTION USING ERRCODE = 'AS999', MESSAGE = 'TFALLO T6b: v_crop_moisture_range no calculó 17.9-25.0 para franco con p=0.55';
    END IF;
    RAISE NOTICE 'OK T6  pH simulado (latest_soil_ph) y rango de humedad FAO-56';

    -- ------------------------------------------------------------
    -- T7: motor de recomendación (reglas estrictas de la guía 4.1)
    -- ------------------------------------------------------------
    INSERT INTO recommendation_runs (parcel_id, soil_window_days, rainfall_window_days, window_end)
    VALUES (v_parcel, 7, 30, '2026-11-12') RETURNING id INTO v_run;

    -- 7a: evaluación válida (3 in_range + 1 below) -> condicionado, con campos de IA
    INSERT INTO recommendation_results (run_id, crop_id, variables_ok, classification,
                                        ml_suitability_score, projected_days, future_risk_summary)
    VALUES (v_run, v_crop, 3, 'condicionado', 78.50, 110, 'Riesgo climático bajo');
    INSERT INTO recommendation_checks (run_id, crop_id, variable, measured, status, origin, is_simulated, advice_id) VALUES
        (v_run, v_crop, 'soil_temperature', 23.5, 'in_range', 'estaca',     false, NULL),
        (v_run, v_crop, 'soil_moisture',    14.0, 'below',    'estaca',     false, v_advice),
        (v_run, v_crop, 'soil_ph',           6.4, 'in_range', 'simulado',   true,  NULL),
        (v_run, v_crop, 'rainfall',         68.5, 'in_range', 'nasa_power', false, NULL);
    SET CONSTRAINTS ALL IMMEDIATE;
    SET CONSTRAINTS ALL DEFERRED;

    -- 7b: con variable no evaluada (null, nunca 0): 3 in_range + 1 not_evaluated
    INSERT INTO recommendation_results (run_id, crop_id, variables_ok, classification)
    VALUES (v_run, v_crop2, 3, 'condicionado');
    INSERT INTO recommendation_checks (run_id, crop_id, variable, measured, status, origin, is_simulated) VALUES
        (v_run, v_crop2, 'soil_temperature', 23.5, 'in_range',      'estaca',     false),
        (v_run, v_crop2, 'soil_moisture',    20.0, 'in_range',      'estaca',     false),
        (v_run, v_crop2, 'soil_ph',           6.4, 'in_range',      'simulado',   true),
        (v_run, v_crop2, 'rainfall',         NULL, 'not_evaluated', 'nasa_power', false);
    SET CONSTRAINTS ALL IMMEDIATE;
    SET CONSTRAINTS ALL DEFERRED;
    RAISE NOTICE 'OK T7a evaluaciones válidas aceptadas (incluida una con not_evaluated)';

    -- Nueva corrida para probar rechazos
    INSERT INTO recommendation_runs (parcel_id, soil_window_days, rainfall_window_days, window_end)
    VALUES (v_parcel, 7, 30, '2026-11-12') RETURNING id INTO v_run;

    -- 7c: solo 1 variable -> debe rechazarse al confirmar (exige las 4)
    BEGIN
        INSERT INTO recommendation_results (run_id, crop_id, variables_ok, classification)
        VALUES (v_run, v_crop, 1, 'no_recomendado');
        INSERT INTO recommendation_checks (run_id, crop_id, variable, measured, status, origin)
        VALUES (v_run, v_crop, 'soil_ph', 6.4, 'in_range', 'simulado');
        SET CONSTRAINTS ALL IMMEDIATE;
        RAISE EXCEPTION USING ERRCODE = 'AS999', MESSAGE = 'TFALLO T7c: se aceptó un cultivo con menos de 4 variables';
    EXCEPTION WHEN raise_exception THEN
        GET STACKED DIAGNOSTICS v_txt = MESSAGE_TEXT;
        IF v_txt NOT LIKE '%4 variables%' THEN
            RAISE EXCEPTION USING ERRCODE = 'AS999', MESSAGE = 'TFALLO T7c: error inesperado: ' || v_txt;
        END IF;
    END;
    SET CONSTRAINTS ALL DEFERRED;

    -- 7d: variables_ok declarado no coincide con los checks in_range
    BEGIN
        INSERT INTO recommendation_results (run_id, crop_id, variables_ok, classification)
        VALUES (v_run, v_crop, 3, 'condicionado');
        INSERT INTO recommendation_checks (run_id, crop_id, variable, measured, status, origin) VALUES
            (v_run, v_crop, 'soil_temperature', 23.5, 'in_range', 'estaca'),
            (v_run, v_crop, 'soil_moisture',    14.0, 'below',    'estaca'),
            (v_run, v_crop, 'soil_ph',           6.4, 'below',    'simulado'),
            (v_run, v_crop, 'rainfall',         68.5, 'below',    'nasa_power');
        SET CONSTRAINTS ALL IMMEDIATE;
        RAISE EXCEPTION USING ERRCODE = 'AS999', MESSAGE = 'TFALLO T7d: se aceptó variables_ok inconsistente con los checks';
    EXCEPTION WHEN raise_exception THEN
        GET STACKED DIAGNOSTICS v_txt = MESSAGE_TEXT;
        IF v_txt NOT LIKE '%no coincide%' THEN
            RAISE EXCEPTION USING ERRCODE = 'AS999', MESSAGE = 'TFALLO T7d: error inesperado: ' || v_txt;
        END IF;
    END;
    SET CONSTRAINTS ALL DEFERRED;

    -- 7e: clasificación incoherente con variables_ok
    BEGIN
        INSERT INTO recommendation_results (run_id, crop_id, variables_ok, classification)
        VALUES (v_run, v_crop, 4, 'condicionado');
        RAISE EXCEPTION USING ERRCODE = 'AS999', MESSAGE = 'TFALLO T7e: se aceptó 4 variables como condicionado';
    EXCEPTION WHEN check_violation THEN NULL; END;

    -- 7f: not_evaluated con measured = 0 (debe ser NULL)
    BEGIN
        INSERT INTO recommendation_results (run_id, crop_id, variables_ok, classification)
        VALUES (v_run, v_crop, 0, 'no_recomendado');
        INSERT INTO recommendation_checks (run_id, crop_id, variable, measured, status)
        VALUES (v_run, v_crop, 'rainfall', 0, 'not_evaluated');
        RAISE EXCEPTION USING ERRCODE = 'AS999', MESSAGE = 'TFALLO T7f: se aceptó not_evaluated con measured = 0';
    EXCEPTION WHEN check_violation THEN NULL; END;

    -- 7g: campos de IA fuera de rango
    BEGIN
        UPDATE recommendation_results SET ml_suitability_score = 999.99
        WHERE run_id = (SELECT run_id FROM recommendation_results WHERE ml_suitability_score IS NOT NULL LIMIT 1);
        RAISE EXCEPTION USING ERRCODE = 'AS999', MESSAGE = 'TFALLO T7g: se aceptó ml_suitability_score = 999.99';
    EXCEPTION WHEN check_violation THEN NULL; END;
    BEGIN
        UPDATE recommendation_results SET projected_days = 0
        WHERE run_id = (SELECT run_id FROM recommendation_results WHERE projected_days IS NOT NULL LIMIT 1);
        RAISE EXCEPTION USING ERRCODE = 'AS999', MESSAGE = 'TFALLO T7g: se aceptó projected_days = 0';
    EXCEPTION WHEN check_violation THEN NULL; END;
    RAISE NOTICE 'OK T7b rechazos: <4 variables, variables_ok inconsistente, clasificación, not_evaluated=0, IA fuera de rango';

    -- ------------------------------------------------------------
    -- T8: parcel_crops y alertas por parcela (Org A)
    -- ------------------------------------------------------------
    PERFORM set_config('app.org_id', v_org_a::text, true);
    INSERT INTO parcel_crops (parcel_id, crop_id, status, sown_at) VALUES (v_parcel, v_crop, 'activo', '2026-11-01');
    BEGIN
        INSERT INTO parcel_crops (parcel_id, crop_id, status) VALUES (v_parcel, v_crop, 'activo');
        RAISE EXCEPTION USING ERRCODE = 'AS999', MESSAGE = 'TFALLO T8a: parcel_crops duplicado aceptado';
    EXCEPTION WHEN unique_violation THEN NULL; END;

    INSERT INTO alerts (parcel_id, kind, severity, payload)
    VALUES (v_parcel, 'clima_adverso', 'aviso', '{"motivo":"lluvia baja"}');
    INSERT INTO alerts (stake_id, kind, severity) VALUES (v_stake, 'bateria_baja', 'info');
    BEGIN
        INSERT INTO alerts (kind, severity) VALUES ('sin_reporte', 'info');
        RAISE EXCEPTION USING ERRCODE = 'AS999', MESSAGE = 'TFALLO T8b: alerta sin estaca ni parcela aceptada';
    EXCEPTION WHEN check_violation OR insufficient_privilege THEN NULL; END;   -- la rechaza la política RLS o el CHECK
    RAISE NOTICE 'OK T8  parcel_crops y alertas por parcela / por estaca';

    -- ------------------------------------------------------------
    -- T9: parche v3.3.1 (origin 'dataset_estimado' y alertas abiertas únicas)
    -- ------------------------------------------------------------
    INSERT INTO recommendation_results (run_id, crop_id, variables_ok, classification)
    VALUES (v_run, v_crop, 4, 'recomendado');
    INSERT INTO recommendation_checks (run_id, crop_id, variable, measured, status, origin, is_simulated) VALUES
        (v_run, v_crop, 'soil_temperature', 23.5, 'in_range', 'estaca',           false),
        (v_run, v_crop, 'soil_moisture',    20.0, 'in_range', 'estaca',           false),
        (v_run, v_crop, 'soil_ph',           6.4, 'in_range', 'dataset_estimado', false),
        (v_run, v_crop, 'rainfall',         68.5, 'in_range', 'nasa_power',       false);
    SET CONSTRAINTS ALL IMMEDIATE;
    SET CONSTRAINTS ALL DEFERRED;

    BEGIN   -- duplicado abierto por estaca
        INSERT INTO alerts (stake_id, kind, severity) VALUES (v_stake, 'bateria_baja', 'info');
        RAISE EXCEPTION USING ERRCODE = 'AS999', MESSAGE = 'TFALLO T9a: alerta abierta duplicada por estaca aceptada';
    EXCEPTION WHEN unique_violation THEN NULL; END;

    BEGIN   -- duplicado abierto por parcela (sin estaca)
        INSERT INTO alerts (parcel_id, kind, severity) VALUES (v_parcel, 'clima_adverso', 'aviso');
        RAISE EXCEPTION USING ERRCODE = 'AS999', MESSAGE = 'TFALLO T9b: alerta abierta duplicada por parcela aceptada';
    EXCEPTION WHEN unique_violation THEN NULL; END;

    -- El patrón que deben usar los backends: ON CONFLICT ... DO NOTHING
    INSERT INTO alerts (stake_id, kind, severity) VALUES (v_stake, 'bateria_baja', 'info')
    ON CONFLICT (stake_id, kind) WHERE resolved_at IS NULL AND stake_id IS NOT NULL DO NOTHING;
    GET DIAGNOSTICS v_n = ROW_COUNT;
    IF v_n <> 0 THEN
        RAISE EXCEPTION USING ERRCODE = 'AS999', MESSAGE = 'TFALLO T9c: ON CONFLICT DO NOTHING insertó un duplicado';
    END IF;

    -- Una vez resuelta, se puede abrir una nueva
    UPDATE alerts SET resolved_at = now() WHERE stake_id = v_stake AND kind = 'bateria_baja' AND resolved_at IS NULL;
    INSERT INTO alerts (stake_id, kind, severity) VALUES (v_stake, 'bateria_baja', 'info');
    RAISE NOTICE 'OK T9  origin dataset_estimado aceptado; alertas abiertas únicas por estaca/parcela';

    -- Limpieza de contexto y regreso a superusuario
    PERFORM set_config('app.org_id', '', true);
    RESET ROLE;
    RAISE NOTICE '--------------------------------------------';
    RAISE NOTICE 'TODAS LAS PRUEBAS OK';
END $$;

ROLLBACK;   -- no deja datos de prueba
