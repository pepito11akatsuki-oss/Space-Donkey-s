const API_URL =
  import.meta.env.VITE_BUSINESS_API_URL ||
  'http://127.0.0.1:8002';

export interface Parcel {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  area_ha: number;
  soil_texture: string | null;
  soil_texture_name: string | null;
  created_at: string;
  active_stakes: number;
  open_alerts: number;
}

export async function getParcels(
  accessToken: string
): Promise<Parcel[]> {
  const response = await fetch(
    `${API_URL}/api/v1/parcels`,
    {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    }
  );

  if (!response.ok) {
    throw new Error(
      `Error al consultar parcelas: HTTP ${response.status}`
    );
  }

  const data: unknown = await response.json();

  if (Array.isArray(data)) {
    return data as Parcel[];
  }

  throw new Error(
    'La API devolvió un formato de parcelas inesperado.'
  );
}
