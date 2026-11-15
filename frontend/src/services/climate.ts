const API_URL = `${import.meta.env.VITE_BUSINESS_API_URL || "http://127.0.0.1:8002"}/api/v1`;

export interface ClimateDay {
  obs_date: string;
  precip_mm: number | null;
  origin: string;
  precip_product: string | null;
  air_temp_c: number | null;
  rel_humidity: number | null;
}

export interface ParcelClimateSummary {
  parcel_id: string;
  parcel_name: string;
  latest_soil_reading: unknown | null;
  latest_ph: unknown | null;
  rainfall_30d: {
    precip_total_mm: number | null;
    origin: string;
    precip_product: string | null;
    days_with_data: number;
    window_days: number;
    last_valid_date: string | null;
  } | null;
}

async function apiGet<T>(
  path: string,
  accessToken: string
): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });

  if (!response.ok) {
    throw new Error(`Error HTTP ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function getClimateHistory(
  parcelId: string,
  accessToken: string
): Promise<ClimateDay[]> {
  return apiGet<ClimateDay[]>(
    `/parcels/${encodeURIComponent(parcelId)}/history/rainfall?days=30`,
    accessToken
  );
}

export function getClimateSummary(
  parcelId: string,
  accessToken: string
): Promise<ParcelClimateSummary> {
  return apiGet<ParcelClimateSummary>(
    `/parcels/${encodeURIComponent(parcelId)}/summary`,
    accessToken
  );
}

export interface SoilPhEstimate {
  parcel_id: string;
  ph: number | null;
  source: string;
  estimated: boolean;
  simulated: boolean;
  depth?: string | null;
  message?: string;
}

export function getSoilPhEstimate(
  parcelId: string,
  accessToken: string
): Promise<SoilPhEstimate> {
  return apiGet<SoilPhEstimate>(
    `/parcels/${encodeURIComponent(parcelId)}/soil/ph-estimate`,
    accessToken
  );
}
