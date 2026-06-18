// Lớp gọi OTA Travel Assistant API.
// Base URL + API key đọc từ biến môi trường (.env). Mọi endpoint trừ /health
// đều yêu cầu header X-API-Key.

const BASE_URL = (
  import.meta.env.VITE_OTA_BASE_URL ?? 'https://supabase-ota-travel.onrender.com'
).replace(/\/$/, '');

const API_KEY = import.meta.env.VITE_OTA_API_KEY ?? '';

export class OtaApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = 'OtaApiError';
    this.status = status;
  }
}

export async function otaGet<T>(
  path: string,
  params?: Record<string, string | number | boolean | undefined | null>,
): Promise<T> {
  const url = new URL(BASE_URL + path);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, String(v));
    }
  }

  const res = await fetch(url.toString(), {
    headers: {
      accept: 'application/json',
      ...(API_KEY ? { 'X-API-Key': API_KEY } : {}),
    },
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body?.detail ?? detail;
    } catch {
      /* ignore non-JSON error bodies */
    }
    throw new OtaApiError(res.status, detail);
  }

  return res.json() as Promise<T>;
}

export const hasApiKey = () => API_KEY.length > 0;
