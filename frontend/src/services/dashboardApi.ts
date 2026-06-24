const BACKEND_BASE_URL = (import.meta.env.VITE_BACKEND_BASE_URL ?? 'http://localhost:8000').replace(/\/$/, '');

export interface OverviewResponse {
  csat: number;
  latency: number;
  ttft: number;
  booking: number;
}

export async function getOverview(token: string | null) {
  const headers: Record<string, string> = { accept: 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${BACKEND_BASE_URL}/dashboard/overview`, { headers });
  if (!res.ok) throw new Error(`Dashboard overview call failed: ${res.statusText}`);
  return (await res.json()).data;
}

export async function getDayAnalysis(month: number, token: string | null) {
  const headers: Record<string, string> = { accept: 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${BACKEND_BASE_URL}/dashboard/analysis/day?month=${month}`, { headers });
  if (!res.ok) throw new Error(`Dashboard day analysis failed: ${res.statusText}`);
  return (await res.json()).data;
}

export async function getMonthAnalysis(year: number, token: string | null) {
  const headers: Record<string, string> = { accept: 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${BACKEND_BASE_URL}/dashboard/analysis/month?year=${year}`, { headers });
  if (!res.ok) throw new Error(`Dashboard month analysis failed: ${res.statusText}`);
  return (await res.json()).data;
}
