-- =====================================================================

-- SEMILLAS DE LOS 22 CULTIVOS + RANGOS p05-p95 + PARÁMETROS FAO-56

-- Ejecutar como agrostake_owner sobre agrostake v3.3

-- =====================================================================


INSERT INTO crops (common_name_es, dataset_label, cycle_days_min, cycle_days_max, source_id)
VALUES ('Manzana', 'apple', 150, 180, (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop'))
ON CONFLICT (dataset_label) DO UPDATE
SET cycle_days_min = EXCLUDED.cycle_days_min, cycle_days_max = EXCLUDED.cycle_days_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'soil_temperature', 21.17, 23.83, '°C', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'apple'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'soil_ph', 5.56, 6.4, 'pH', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'apple'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'rainfall', 102.24, 123.6, 'mm', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'apple'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_irrigation_params (crop_id, depletion_fraction_p, source_id)
SELECT id, 0.5, (SELECT id FROM data_sources WHERE name LIKE 'FAO-56%')
FROM crops WHERE dataset_label = 'apple'
ON CONFLICT (crop_id) DO UPDATE SET depletion_fraction_p = EXCLUDED.depletion_fraction_p;

INSERT INTO crops (common_name_es, dataset_label, cycle_days_min, cycle_days_max, source_id)
VALUES ('Plátano', 'banana', 270, 365, (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop'))
ON CONFLICT (dataset_label) DO UPDATE
SET cycle_days_min = EXCLUDED.cycle_days_min, cycle_days_max = EXCLUDED.cycle_days_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'soil_temperature', 25.15, 29.42, '°C', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'banana'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'soil_ph', 5.57, 6.44, 'pH', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'banana'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'rainfall', 90.81, 119.0, 'mm', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'banana'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_irrigation_params (crop_id, depletion_fraction_p, source_id)
SELECT id, 0.35, (SELECT id FROM data_sources WHERE name LIKE 'FAO-56%')
FROM crops WHERE dataset_label = 'banana'
ON CONFLICT (crop_id) DO UPDATE SET depletion_fraction_p = EXCLUDED.depletion_fraction_p;

INSERT INTO crops (common_name_es, dataset_label, cycle_days_min, cycle_days_max, source_id)
VALUES ('Lenteja negra', 'blackgram', 75, 90, (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop'))
ON CONFLICT (dataset_label) DO UPDATE
SET cycle_days_min = EXCLUDED.cycle_days_min, cycle_days_max = EXCLUDED.cycle_days_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'soil_temperature', 25.65, 34.14, '°C', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'blackgram'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'soil_ph', 6.54, 7.71, 'pH', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'blackgram'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'rainfall', 61.7, 74.22, 'mm', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'blackgram'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_irrigation_params (crop_id, depletion_fraction_p, source_id)
SELECT id, 0.45, (SELECT id FROM data_sources WHERE name LIKE 'FAO-56%')
FROM crops WHERE dataset_label = 'blackgram'
ON CONFLICT (crop_id) DO UPDATE SET depletion_fraction_p = EXCLUDED.depletion_fraction_p;

INSERT INTO crops (common_name_es, dataset_label, cycle_days_min, cycle_days_max, source_id)
VALUES ('Garbanzo', 'chickpea', 90, 110, (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop'))
ON CONFLICT (dataset_label) DO UPDATE
SET cycle_days_min = EXCLUDED.cycle_days_min, cycle_days_max = EXCLUDED.cycle_days_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'soil_temperature', 17.16, 20.72, '°C', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'chickpea'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'soil_ph', 6.18, 8.74, 'pH', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'chickpea'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'rainfall', 68.47, 93.36, 'mm', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'chickpea'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_irrigation_params (crop_id, depletion_fraction_p, source_id)
SELECT id, 0.5, (SELECT id FROM data_sources WHERE name LIKE 'FAO-56%')
FROM crops WHERE dataset_label = 'chickpea'
ON CONFLICT (crop_id) DO UPDATE SET depletion_fraction_p = EXCLUDED.depletion_fraction_p;

INSERT INTO crops (common_name_es, dataset_label, cycle_days_min, cycle_days_max, source_id)
VALUES ('Coco', 'coconut', 365, 365, (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop'))
ON CONFLICT (dataset_label) DO UPDATE
SET cycle_days_min = EXCLUDED.cycle_days_min, cycle_days_max = EXCLUDED.cycle_days_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'soil_temperature', 25.1, 29.53, '°C', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'coconut'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'soil_ph', 5.55, 6.42, 'pH', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'coconut'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'rainfall', 134.03, 224.32, 'mm', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'coconut'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_irrigation_params (crop_id, depletion_fraction_p, source_id)
SELECT id, 0.5, (SELECT id FROM data_sources WHERE name LIKE 'FAO-56%')
FROM crops WHERE dataset_label = 'coconut'
ON CONFLICT (crop_id) DO UPDATE SET depletion_fraction_p = EXCLUDED.depletion_fraction_p;

INSERT INTO crops (common_name_es, dataset_label, cycle_days_min, cycle_days_max, source_id)
VALUES ('Café', 'coffee', 270, 365, (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop'))
ON CONFLICT (dataset_label) DO UPDATE
SET cycle_days_min = EXCLUDED.cycle_days_min, cycle_days_max = EXCLUDED.cycle_days_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'soil_temperature', 23.18, 27.58, '°C', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'coffee'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'soil_ph', 6.08, 7.46, 'pH', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'coffee'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'rainfall', 120.6, 194.92, 'mm', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'coffee'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_irrigation_params (crop_id, depletion_fraction_p, source_id)
SELECT id, 0.4, (SELECT id FROM data_sources WHERE name LIKE 'FAO-56%')
FROM crops WHERE dataset_label = 'coffee'
ON CONFLICT (crop_id) DO UPDATE SET depletion_fraction_p = EXCLUDED.depletion_fraction_p;

INSERT INTO crops (common_name_es, dataset_label, cycle_days_min, cycle_days_max, source_id)
VALUES ('Algodón', 'cotton', 150, 180, (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop'))
ON CONFLICT (dataset_label) DO UPDATE
SET cycle_days_min = EXCLUDED.cycle_days_min, cycle_days_max = EXCLUDED.cycle_days_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'soil_temperature', 22.14, 25.69, '°C', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'cotton'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'soil_ph', 6.0, 7.95, 'pH', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'cotton'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'rainfall', 62.64, 97.81, 'mm', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'cotton'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_irrigation_params (crop_id, depletion_fraction_p, source_id)
SELECT id, 0.65, (SELECT id FROM data_sources WHERE name LIKE 'FAO-56%')
FROM crops WHERE dataset_label = 'cotton'
ON CONFLICT (crop_id) DO UPDATE SET depletion_fraction_p = EXCLUDED.depletion_fraction_p;

INSERT INTO crops (common_name_es, dataset_label, cycle_days_min, cycle_days_max, source_id)
VALUES ('Uva', 'grapes', 150, 180, (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop'))
ON CONFLICT (dataset_label) DO UPDATE
SET cycle_days_min = EXCLUDED.cycle_days_min, cycle_days_max = EXCLUDED.cycle_days_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'soil_temperature', 9.94, 40.69, '°C', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'grapes'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'soil_ph', 5.56, 6.48, 'pH', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'grapes'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'rainfall', 65.52, 74.41, 'mm', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'grapes'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_irrigation_params (crop_id, depletion_fraction_p, source_id)
SELECT id, 0.45, (SELECT id FROM data_sources WHERE name LIKE 'FAO-56%')
FROM crops WHERE dataset_label = 'grapes'
ON CONFLICT (crop_id) DO UPDATE SET depletion_fraction_p = EXCLUDED.depletion_fraction_p;

INSERT INTO crops (common_name_es, dataset_label, cycle_days_min, cycle_days_max, source_id)
VALUES ('Yute', 'jute', 120, 150, (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop'))
ON CONFLICT (dataset_label) DO UPDATE
SET cycle_days_min = EXCLUDED.cycle_days_min, cycle_days_max = EXCLUDED.cycle_days_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'soil_temperature', 23.17, 26.83, '°C', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'jute'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'soil_ph', 6.07, 7.38, 'pH', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'jute'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'rainfall', 151.87, 196.68, 'mm', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'jute'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_irrigation_params (crop_id, depletion_fraction_p, source_id)
SELECT id, 0.45, (SELECT id FROM data_sources WHERE name LIKE 'FAO-56%')
FROM crops WHERE dataset_label = 'jute'
ON CONFLICT (crop_id) DO UPDATE SET depletion_fraction_p = EXCLUDED.depletion_fraction_p;

INSERT INTO crops (common_name_es, dataset_label, cycle_days_min, cycle_days_max, source_id)
VALUES ('Frijol', 'kidneybeans', 75, 95, (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop'))
ON CONFLICT (dataset_label) DO UPDATE
SET cycle_days_min = EXCLUDED.cycle_days_min, cycle_days_max = EXCLUDED.cycle_days_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'soil_temperature', 15.79, 24.33, '°C', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'kidneybeans'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'soil_ph', 5.52, 5.97, 'pH', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'kidneybeans'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'rainfall', 63.35, 143.87, 'mm', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'kidneybeans'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_irrigation_params (crop_id, depletion_fraction_p, source_id)
SELECT id, 0.45, (SELECT id FROM data_sources WHERE name LIKE 'FAO-56%')
FROM crops WHERE dataset_label = 'kidneybeans'
ON CONFLICT (crop_id) DO UPDATE SET depletion_fraction_p = EXCLUDED.depletion_fraction_p;

INSERT INTO crops (common_name_es, dataset_label, cycle_days_min, cycle_days_max, source_id)
VALUES ('Lenteja', 'lentil', 95, 115, (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop'))
ON CONFLICT (dataset_label) DO UPDATE
SET cycle_days_min = EXCLUDED.cycle_days_min, cycle_days_max = EXCLUDED.cycle_days_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'soil_temperature', 18.43, 29.22, '°C', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'lentil'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'soil_ph', 6.06, 7.73, 'pH', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'lentil'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'rainfall', 36.08, 53.32, 'mm', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'lentil'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_irrigation_params (crop_id, depletion_fraction_p, source_id)
SELECT id, 0.5, (SELECT id FROM data_sources WHERE name LIKE 'FAO-56%')
FROM crops WHERE dataset_label = 'lentil'
ON CONFLICT (crop_id) DO UPDATE SET depletion_fraction_p = EXCLUDED.depletion_fraction_p;

INSERT INTO crops (common_name_es, dataset_label, cycle_days_min, cycle_days_max, source_id)
VALUES ('Maíz', 'maize', 95, 120, (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop'))
ON CONFLICT (dataset_label) DO UPDATE
SET cycle_days_min = EXCLUDED.cycle_days_min, cycle_days_max = EXCLUDED.cycle_days_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'soil_temperature', 18.28, 25.98, '°C', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'maize'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'soil_ph', 5.59, 6.87, 'pH', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'maize'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'rainfall', 63.03, 108.52, 'mm', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'maize'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_irrigation_params (crop_id, depletion_fraction_p, source_id)
SELECT id, 0.55, (SELECT id FROM data_sources WHERE name LIKE 'FAO-56%')
FROM crops WHERE dataset_label = 'maize'
ON CONFLICT (crop_id) DO UPDATE SET depletion_fraction_p = EXCLUDED.depletion_fraction_p;

INSERT INTO crops (common_name_es, dataset_label, cycle_days_min, cycle_days_max, source_id)
VALUES ('Mango', 'mango', 150, 180, (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop'))
ON CONFLICT (dataset_label) DO UPDATE
SET cycle_days_min = EXCLUDED.cycle_days_min, cycle_days_max = EXCLUDED.cycle_days_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'soil_temperature', 27.35, 35.54, '°C', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'mango'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'soil_ph', 4.67, 6.82, 'pH', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'mango'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'rainfall', 89.97, 100.22, 'mm', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'mango'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_irrigation_params (crop_id, depletion_fraction_p, source_id)
SELECT id, 0.5, (SELECT id FROM data_sources WHERE name LIKE 'FAO-56%')
FROM crops WHERE dataset_label = 'mango'
ON CONFLICT (crop_id) DO UPDATE SET depletion_fraction_p = EXCLUDED.depletion_fraction_p;

INSERT INTO crops (common_name_es, dataset_label, cycle_days_min, cycle_days_max, source_id)
VALUES ('Frijol polilla', 'mothbeans', 70, 90, (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop'))
ON CONFLICT (dataset_label) DO UPDATE
SET cycle_days_min = EXCLUDED.cycle_days_min, cycle_days_max = EXCLUDED.cycle_days_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'soil_temperature', 24.47, 31.23, '°C', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'mothbeans'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'soil_ph', 3.69, 9.41, 'pH', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'mothbeans'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'rainfall', 32.67, 72.22, 'mm', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'mothbeans'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_irrigation_params (crop_id, depletion_fraction_p, source_id)
SELECT id, 0.45, (SELECT id FROM data_sources WHERE name LIKE 'FAO-56%')
FROM crops WHERE dataset_label = 'mothbeans'
ON CONFLICT (crop_id) DO UPDATE SET depletion_fraction_p = EXCLUDED.depletion_fraction_p;

INSERT INTO crops (common_name_es, dataset_label, cycle_days_min, cycle_days_max, source_id)
VALUES ('Frijol mungo', 'mungbean', 65, 80, (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop'))
ON CONFLICT (dataset_label) DO UPDATE
SET cycle_days_min = EXCLUDED.cycle_days_min, cycle_days_max = EXCLUDED.cycle_days_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'soil_temperature', 27.11, 29.87, '°C', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'mungbean'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'soil_ph', 6.27, 7.17, 'pH', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'mungbean'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'rainfall', 37.23, 58.55, 'mm', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'mungbean'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_irrigation_params (crop_id, depletion_fraction_p, source_id)
SELECT id, 0.45, (SELECT id FROM data_sources WHERE name LIKE 'FAO-56%')
FROM crops WHERE dataset_label = 'mungbean'
ON CONFLICT (crop_id) DO UPDATE SET depletion_fraction_p = EXCLUDED.depletion_fraction_p;

INSERT INTO crops (common_name_es, dataset_label, cycle_days_min, cycle_days_max, source_id)
VALUES ('Melón', 'muskmelon', 75, 90, (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop'))
ON CONFLICT (dataset_label) DO UPDATE
SET cycle_days_min = EXCLUDED.cycle_days_min, cycle_days_max = EXCLUDED.cycle_days_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'soil_temperature', 27.11, 29.87, '°C', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'muskmelon'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'soil_ph', 6.04, 6.74, 'pH', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'muskmelon'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'rainfall', 20.76, 28.99, 'mm', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'muskmelon'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_irrigation_params (crop_id, depletion_fraction_p, source_id)
SELECT id, 0.4, (SELECT id FROM data_sources WHERE name LIKE 'FAO-56%')
FROM crops WHERE dataset_label = 'muskmelon'
ON CONFLICT (crop_id) DO UPDATE SET depletion_fraction_p = EXCLUDED.depletion_fraction_p;

INSERT INTO crops (common_name_es, dataset_label, cycle_days_min, cycle_days_max, source_id)
VALUES ('Naranja', 'orange', 240, 300, (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop'))
ON CONFLICT (dataset_label) DO UPDATE
SET cycle_days_min = EXCLUDED.cycle_days_min, cycle_days_max = EXCLUDED.cycle_days_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'soil_temperature', 11.02, 34.08, '°C', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'orange'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'soil_ph', 6.12, 7.86, 'pH', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'orange'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'rainfall', 101.15, 119.04, 'mm', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'orange'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_irrigation_params (crop_id, depletion_fraction_p, source_id)
SELECT id, 0.5, (SELECT id FROM data_sources WHERE name LIKE 'FAO-56%')
FROM crops WHERE dataset_label = 'orange'
ON CONFLICT (crop_id) DO UPDATE SET depletion_fraction_p = EXCLUDED.depletion_fraction_p;

INSERT INTO crops (common_name_es, dataset_label, cycle_days_min, cycle_days_max, source_id)
VALUES ('Papaya', 'papaya', 240, 300, (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop'))
ON CONFLICT (dataset_label) DO UPDATE
SET cycle_days_min = EXCLUDED.cycle_days_min, cycle_days_max = EXCLUDED.cycle_days_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'soil_temperature', 23.68, 42.94, '°C', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'papaya'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'soil_ph', 6.52, 6.99, 'pH', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'papaya'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'rainfall', 50.96, 240.49, 'mm', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'papaya'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_irrigation_params (crop_id, depletion_fraction_p, source_id)
SELECT id, 0.4, (SELECT id FROM data_sources WHERE name LIKE 'FAO-56%')
FROM crops WHERE dataset_label = 'papaya'
ON CONFLICT (crop_id) DO UPDATE SET depletion_fraction_p = EXCLUDED.depletion_fraction_p;

INSERT INTO crops (common_name_es, dataset_label, cycle_days_min, cycle_days_max, source_id)
VALUES ('Gandul', 'pigeonpeas', 150, 180, (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop'))
ON CONFLICT (dataset_label) DO UPDATE
SET cycle_days_min = EXCLUDED.cycle_days_min, cycle_days_max = EXCLUDED.cycle_days_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'soil_temperature', 19.03, 36.21, '°C', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'pigeonpeas'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'soil_ph', 4.67, 7.17, 'pH', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'pigeonpeas'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'rainfall', 94.4, 195.58, 'mm', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'pigeonpeas'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_irrigation_params (crop_id, depletion_fraction_p, source_id)
SELECT id, 0.5, (SELECT id FROM data_sources WHERE name LIKE 'FAO-56%')
FROM crops WHERE dataset_label = 'pigeonpeas'
ON CONFLICT (crop_id) DO UPDATE SET depletion_fraction_p = EXCLUDED.depletion_fraction_p;

INSERT INTO crops (common_name_es, dataset_label, cycle_days_min, cycle_days_max, source_id)
VALUES ('Granada', 'pomegranate', 180, 240, (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop'))
ON CONFLICT (dataset_label) DO UPDATE
SET cycle_days_min = EXCLUDED.cycle_days_min, cycle_days_max = EXCLUDED.cycle_days_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'soil_temperature', 18.4, 24.82, '°C', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'pomegranate'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'soil_ph', 5.68, 7.13, 'pH', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'pomegranate'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'rainfall', 102.86, 111.98, 'mm', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'pomegranate'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_irrigation_params (crop_id, depletion_fraction_p, source_id)
SELECT id, 0.5, (SELECT id FROM data_sources WHERE name LIKE 'FAO-56%')
FROM crops WHERE dataset_label = 'pomegranate'
ON CONFLICT (crop_id) DO UPDATE SET depletion_fraction_p = EXCLUDED.depletion_fraction_p;

INSERT INTO crops (common_name_es, dataset_label, cycle_days_min, cycle_days_max, source_id)
VALUES ('Arroz', 'rice', 110, 140, (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop'))
ON CONFLICT (dataset_label) DO UPDATE
SET cycle_days_min = EXCLUDED.cycle_days_min, cycle_days_max = EXCLUDED.cycle_days_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'soil_temperature', 20.28, 26.73, '°C', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'rice'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'soil_ph', 5.11, 7.63, 'pH', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'rice'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'rainfall', 185.2, 290.71, 'mm', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'rice'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_irrigation_params (crop_id, depletion_fraction_p, source_id)
SELECT id, 0.2, (SELECT id FROM data_sources WHERE name LIKE 'FAO-56%')
FROM crops WHERE dataset_label = 'rice'
ON CONFLICT (crop_id) DO UPDATE SET depletion_fraction_p = EXCLUDED.depletion_fraction_p;

INSERT INTO crops (common_name_es, dataset_label, cycle_days_min, cycle_days_max, source_id)
VALUES ('Sandía', 'watermelon', 75, 90, (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop'))
ON CONFLICT (dataset_label) DO UPDATE
SET cycle_days_min = EXCLUDED.cycle_days_min, cycle_days_max = EXCLUDED.cycle_days_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'soil_temperature', 24.29, 26.82, '°C', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'watermelon'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'soil_ph', 6.07, 6.93, 'pH', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'watermelon'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_requirements (crop_id, variable, optimal_min, optimal_max, unit, method, source_id)
SELECT id, 'rainfall', 41.15, 58.99, 'mm', 'p05-p95 (n=100)', (SELECT id FROM data_sources WHERE name = 'FAO EcoCrop')
FROM crops WHERE dataset_label = 'watermelon'
ON CONFLICT (crop_id, variable) DO UPDATE SET optimal_min = EXCLUDED.optimal_min, optimal_max = EXCLUDED.optimal_max;

INSERT INTO crop_irrigation_params (crop_id, depletion_fraction_p, source_id)
SELECT id, 0.4, (SELECT id FROM data_sources WHERE name LIKE 'FAO-56%')
FROM crops WHERE dataset_label = 'watermelon'
ON CONFLICT (crop_id) DO UPDATE SET depletion_fraction_p = EXCLUDED.depletion_fraction_p;