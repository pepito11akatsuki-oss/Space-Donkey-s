"""
Pruebas unitarias para la conversión de calibración de humedad de suelo.
"""
import unittest
from calibration import convert_soil_moisture

class TestSoilCalibration(unittest.TestCase):
    def test_convert_soil_moisture_normal(self):
        # ADC seco = 4095, ADC agua = 1200
        params = {"adc_dry": 4095, "adc_wet": 1200}
        
        # Lectura intermedia (ej. 2647, mitad exacta)
        pct = convert_soil_moisture(2647, params)
        self.assertIsNotNone(pct)
        self.assertAlmostEqual(pct, 50.0, delta=1.0)

    def test_convert_soil_moisture_extremes(self):
        params = {"adc_dry": 4095, "adc_wet": 1200}
        
        # Muy seco (>= 4095)
        self.assertEqual(convert_soil_moisture(4100, params), 0.0)
        
        # Muy húmedo (<= 1200)
        self.assertEqual(convert_soil_moisture(1000, params), 100.0)

    def test_convert_soil_moisture_none(self):
        self.assertIsNone(convert_soil_moisture(None, {"adc_dry": 4095, "adc_wet": 1200}))

if __name__ == "__main__":
    unittest.main()
