import os
import json
import time
import joblib
import requests
import numpy as np
from datetime import datetime
from typing import Dict, Any, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "models")

scaler_agro = joblib.load(os.path.join(MODELS_DIR, "scaler_agro.pkl"))
modelo_cultivos = joblib.load(os.path.join(MODELS_DIR, "modelo_cultivos.pkl"))
le_cultivos = joblib.load(os.path.join(MODELS_DIR, "label_encoder_cultivos.pkl"))

with open(os.path.join(MODELS_DIR, "catalogo_cultivos.json"), "r", encoding="utf-8") as f:
    CATALOGO = json.load(f)

_CACHE_NASA = {}

def obtener_climatologia_futura_nasa(lat: float, lon: float) -> Dict[int, Dict[str, float]]:
    key = (round(lat, 2), round(lon, 2))
    if key in _CACHE_NASA and (time.time() - _CACHE_NASA[key]["ts"] < 3600):
        return _CACHE_NASA[key]["data"]

    url = (
        f"https://power.larc.nasa.gov/api/temporal/climatology/point"
        f"?parameters=T2M,PRECTOTCORR,RH2M&community=AG&longitude={lon}&latitude={lat}&format=JSON"
    )
    meses_map = {
        "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
        "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12
    }

    try:
        resp = requests.get(url, timeout=4)
        resp.raise_for_status()
        params = resp.json()["properties"]["parameter"]
        perfil_mensual = {}
        for m_str, m_num in meses_map.items():
            lluvia_dia = float(params["PRECTOTCORR"].get(m_str, 2.0))
            perfil_mensual[m_num] = {
                "temp_c": float(params["T2M"].get(m_str, 22.0)),
                "rain_mm_mes": max(0.0, lluvia_dia * 30.0),
                "rh_pct": float(params["RH2M"].get(m_str, 60.0)),
            }
        _CACHE_NASA[key] = {"ts": time.time(), "data": perfil_mensual}
        return perfil_mensual
    except Exception:
        return {m: {"temp_c": 22.5, "rain_mm_mes": 75.0, "rh_pct": 62.0} for m in range(1, 13)}


def proyectar_condiciones_ciclo(
    lat: float,
    lon: float,
    dias_ciclo: int,
    sensor_temp_hoy: Optional[float],
    sensor_humedad_hoy: Optional[float],
) -> Dict[str, float]:
    perfil_nasa = obtener_climatologia_futura_nasa(lat, lon)
    mes_inicio = datetime.utcnow().month
    num_meses = max(1, round(dias_ciclo / 30))

    temps_futuras, lluvias_mensuales, humedades_futuras = [], [], []
    for i in range(num_meses):
        mes_idx = ((mes_inicio - 1 + i) % 12) + 1
        datos_m = perfil_nasa[mes_idx]
        temps_futuras.append(datos_m["temp_c"])
        lluvias_mensuales.append(datos_m["rain_mm_mes"])
        humedades_futuras.append(datos_m["rh_pct"])

    temp_nasa_ciclo = float(np.mean(temps_futuras))
    temp_proyectada = (0.35 * sensor_temp_hoy + 0.65 * temp_nasa_ciclo) if sensor_temp_hoy is not None else temp_nasa_ciclo

    humedad_nasa_ciclo = float(np.mean(humedades_futuras))
    humedad_proyectada = (0.45 * sensor_humedad_hoy + 0.55 * humedad_nasa_ciclo) if sensor_humedad_hoy is not None else humedad_nasa_ciclo

    lluvia_proyectada_mm = float(np.mean(lluvias_mensuales))

    return {
        "temp_ciclo_c": round(temp_proyectada, 2),
        "humedad_ciclo_pct": round(humedad_proyectada, 2),
        "lluvia_ciclo_mm": round(lluvia_proyectada_mm, 2),
        "meses_evaluados": num_meses,
    }


def _calcular_afinidad_variable(val: Optional[float], r_min: float, r_max: float) -> float:
    """Devuelve 1.0 si está en el centro del rango óptimo, 0.75-0.95 en los bordes, y decae fuera de rango."""
    if val is None:
        return 0.0
    centro = (r_min + r_max) / 2.0
    amplitud = max((r_max - r_min) / 2.0, 0.5)
    distancia_norm = abs(val - centro) / amplitud
    if distancia_norm <= 1.0:
        return 1.0 - 0.25 * (distancia_norm ** 2)
    exceso = distancia_norm - 1.0
    return max(0.0, 0.65 * np.exp(-0.8 * exceso))


def evaluar_viabilidad_temporal(
    lat: float,
    lon: float,
    sensor_temp_c: Optional[float],
    sensor_humedad_pct: Optional[float],
    soil_ph: Optional[float],
    ph_is_simulated: bool = True,
    cultivo_filtro: Optional[str] = None,
) -> Dict[str, Any]:
    warnings = []
    if soil_ph is not None and ph_is_simulated:
        warnings.append(f"El pH ({soil_ph}) es SIMULADO (ph_method='simulado') y debe etiquetarse en UI.")
    if sensor_temp_c is None or sensor_humedad_pct is None:
        warnings.append("Faltan lecturas en vivo de la estaca; se complementó con climatología NASA POWER.")

    resultados = []
    N_NEUTRO, P_NEUTRO, K_NEUTRO = 37.0, 51.0, 32.0

    for label, info in CATALOGO.items():
        if cultivo_filtro and cultivo_filtro not in (label, info["common_name_es"].lower()):
            continue

        dias_avg = info["cycle_days_avg"]
        proy = proyectar_condiciones_ciclo(lat, lon, dias_avg, sensor_temp_c, sensor_humedad_pct)

        x_row = np.array([[
            N_NEUTRO, P_NEUTRO, K_NEUTRO,
            proy["temp_ciclo_c"],
            proy["humedad_ciclo_pct"],
            soil_ph if soil_ph is not None else 6.5,
            proy["lluvia_ciclo_mm"]
        ]])
        x_scaled = scaler_agro.transform(x_row)
        probs = modelo_cultivos.predict_proba(x_scaled)[0]
        clase_idx = list(le_cultivos.classes_).index(label)
        prob_relativa = float(probs[clase_idx]) / max(float(np.max(probs)), 1e-6)

        rangos = info["ranges"]
        evaluacion_vars = {
            "soil_temperature": (proy["temp_ciclo_c"], rangos["soil_temperature"], "°C"),
            "soil_moisture": (proy["humedad_ciclo_pct"], rangos["soil_moisture"], "%"),
            "soil_ph": (soil_ph, rangos["soil_ph"], "pH"),
            "rainfall": (proy["lluvia_ciclo_mm"], rangos["rainfall"], "mm/mes"),
        }

        variables_ok = 0
        checks = []
        consejos = []
        afinidades = []

        for var_name, (val, (r_min, r_max), unit) in evaluacion_vars.items():
            afinidades.append(_calcular_afinidad_variable(val, r_min, r_max))
            if val is None:
                status = "not_evaluated"
                consejos.append(f"Falta dato para evaluar {var_name}.")
            elif r_min <= val <= r_max:
                status = "in_range"
                variables_ok += 1
            elif val < r_min:
                status = "below"
                consejos.append(f"{var_name} proyectado bajo ({val} {unit} vs óptimo {r_min}-{r_max} {unit}).")
            else:
                status = "above"
                consejos.append(f"{var_name} proyectado alto ({val} {unit} vs óptimo {r_min}-{r_max} {unit}).")

            checks.append({
                "variable": var_name,
                "projected_value": val,
                "optimal_range": [r_min, r_max],
                "unit": unit,
                "status": status,
                "is_simulated": (var_name == "soil_ph" and ph_is_simulated),
            })

        afinidad_media = float(np.mean(afinidades))
        ml_score = round((0.80 * afinidad_media + 0.20 * prob_relativa) * 100, 1)

        if variables_ok == 4:
            clasificacion = "recomendado"
            resumen_humano = (
                f"El {info['common_name_es']} es una excelente opción para tu parcela: "
                f"cumple las 4 condiciones ideales durante sus {info['cycle_days_min']}-{info['cycle_days_max']} días "
                f"de cultivo ({ml_score}% de compatibilidad)."
            )
        elif variables_ok == 3:
            clasificacion = "condicionado"
            resumen_humano = (
                f"Puedes sembrar {info['common_name_es']} ({info['cycle_days_min']}-{info['cycle_days_max']} días), "
                f"pero requiere cuidados: cumple 3 de 4 condiciones ({ml_score}% de compatibilidad)."
            )
        else:
            clasificacion = "no_recomendado"
            resumen_humano = (
                f"No te conviene sembrar {info['common_name_es']} en esta temporada: "
                f"solo cumple {variables_ok} de 4 condiciones ({ml_score}% de compatibilidad)."
            )

        resultados.append({
            "dataset_label": label,
            "common_name_es": info["common_name_es"],
            "cycle_days": f"{info['cycle_days_min']}-{info['cycle_days_max']} días",
            "classification": clasificacion,
            "variables_ok": variables_ok,
            "ml_suitability_score": ml_score,
            "projected_climate": proy,
            "checks": checks,
            "recommendations": consejos,
            "justification": resumen_humano,
        })

    resultados.sort(key=lambda r: (r["variables_ok"], r["ml_suitability_score"]), reverse=True)

    return {
        "coordinates": {"lat": lat, "lon": lon},
        "sensor_snapshot_today": {
            "soil_temperature_c": sensor_temp_c,
            "soil_moisture_pct": sensor_humedad_pct,
            "soil_ph": soil_ph,
            "ph_is_simulated": ph_is_simulated,
        },
        "warnings": warnings,
        "top_recommendations": resultados[:5],
        "all_evaluations": resultados,
    }
