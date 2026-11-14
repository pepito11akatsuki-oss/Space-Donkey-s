"""
Calibración y conversión de lecturas crudas de sensores (ADC) a unidades reales (FAO-56).
"""

from typing import Optional

def convert_soil_moisture(raw_adc: Optional[int], calibration_params: dict) -> Optional[float]:
    """
    Convierte el valor ADC crudo a porcentaje volumétrico de humedad (% vol)
    utilizando los parámetros de calibración de dos puntos (seco / agua saturada)
    o curva lineal guardados en sensor_calibrations.params (JSONB).
    """
    if raw_adc is None:
        return None
    
    # Ejemplo de parámetros: {"adc_dry": 4095, "adc_wet": 1200, "method": "linear_two_point"}
    adc_dry = calibration_params.get("adc_dry", 4095)
    adc_wet = calibration_params.get("adc_wet", 1200)
    
    # Restricción física
    if raw_adc >= adc_dry:
        return 0.0
    if raw_adc <= adc_wet:
        return 100.0
        
    # Conversión lineal inversa (ADC alto = seco, ADC bajo = húmedo)
    pct = ((adc_dry - raw_adc) / (adc_dry - adc_wet)) * 100.0
    return round(max(0.0, min(100.0, pct)), 2)
