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
