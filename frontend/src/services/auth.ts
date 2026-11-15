const AUTH_API = import.meta.env.VITE_AUTH_API_URL || 'http://127.0.0.1:8000';

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  org_id: string;
  user_id: string;
  role: 'owner' | 'agronomist' | 'viewer';
}

export async function login(email: string, password: string): Promise<LoginResponse> {
  const response = await fetch(`${AUTH_API}/api/v1/auth/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    if (response.status === 401) {
      throw new Error('Correo o contraseña incorrectos.');
    }
    throw new Error(`No se pudo iniciar sesión. Error HTTP ${response.status}.`);
  }

  return response.json();
}
