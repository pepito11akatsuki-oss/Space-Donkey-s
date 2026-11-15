const API_URL = "http://127.0.0.1:8002/api/v1";

export interface CropVariableCheck {
  variable: string;
  measured: number | null;
  status: string;
  origin: string | null;
  is_simulated: boolean;
  advice_template: string | null;
}

export interface CropRecommendation {
  crop_id: number;
  common_name_es: string;
  scientific_name: string;
  variables_ok: number;
  classification: string;
  evaluation_status?: 'complete' | 'incomplete';
  recommendation_eligible?: boolean;
  ml_suitability_score: number | null;
  projected_days: number | null;
  future_risk_summary: string | null;
  checks: CropVariableCheck[];
}

export interface RecommendationRun {
  id: string;
  soil_window_days: number;
  rainfall_window_days: number;
  window_end: string;
  created_at: string;
  results: CropRecommendation[];
}

export async function getRecommendations(
  parcelId: string,
  accessToken: string
): Promise<RecommendationRun> {
  const response = await fetch(
    `${API_URL}/parcels/${encodeURIComponent(parcelId)}/recommendations`,
    {
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    }
  );

  if (!response.ok) {
    throw new Error(`Error HTTP ${response.status} al consultar recomendaciones`);
  }

  const data: unknown = await response.json();

  if (!Array.isArray(data)) {
    throw new Error('Formato inesperado: se esperaba una lista de análisis.');
  }

  const runs = data as RecommendationRun[];

  if (runs.length === 0) {
    throw new Error('Todavía no existen análisis agrícolas para esta parcela.');
  }

  const latestRun = [...runs].sort(
    (a, b) =>
      new Date(b.created_at).getTime() -
      new Date(a.created_at).getTime()
  )[0];

  if (!latestRun || !Array.isArray(latestRun.results)) {
    throw new Error('El análisis agrícola no contiene resultados válidos.');
  }

  return latestRun;
}

