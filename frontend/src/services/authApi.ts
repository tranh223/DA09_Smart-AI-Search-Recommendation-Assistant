// Auth API service — gọi backend /auth/* endpoints.

const BACKEND_BASE_URL = (
  import.meta.env.VITE_BACKEND_BASE_URL ?? 'http://localhost:8000'
).replace(/\/$/, '');

// ── Types ────────────────────────────────────────────────────────────────────

export interface AuthUser {
  user_id: string;
  name: string;
  [key: string]: unknown;
}

export interface AuthData {
  access_token: string;
  token_type: string;
  role: string;
  user: AuthUser;
}

interface ApiResponse<T> {
  success: boolean;
  request_id: string;
  data?: T;
  error?: { code: string; message: string } | null;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

const TOKEN_KEY = 'vinjourney_token';
const USER_KEY = 'vinjourney_user';
const ROLE_KEY = 'vinjourney_role';

export function saveAuth(data: AuthData) {
  localStorage.setItem(TOKEN_KEY, data.access_token);
  localStorage.setItem(USER_KEY, JSON.stringify(data.user));
  localStorage.setItem(ROLE_KEY, data.role);
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  localStorage.removeItem(ROLE_KEY);
}

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function getStoredUser(): AuthUser | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}

export function getStoredRole(): string | null {
  return localStorage.getItem(ROLE_KEY);
}

// ── API calls ────────────────────────────────────────────────────────────────

export async function apiRegister(
  username: string,
  password: string,
  name: string,
): Promise<AuthData> {
  const res = await fetch(`${BACKEND_BASE_URL}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password, name }),
  });

  const body = (await res.json().catch(() => null)) as ApiResponse<AuthData> | null;

  if (!body?.success || !body.data) {
    throw new Error(body?.error?.message || 'Đăng ký thất bại');
  }

  return body.data;
}

export async function apiLogin(
  username: string,
  password: string,
): Promise<AuthData> {
  const res = await fetch(`${BACKEND_BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });

  const body = (await res.json().catch(() => null)) as ApiResponse<AuthData> | null;

  if (!body?.success || !body.data) {
    throw new Error(body?.error?.message || 'Đăng nhập thất bại');
  }

  return body.data;
}

export async function apiGetMe(token: string): Promise<{
  account: Record<string, unknown>;
  user_profile: AuthUser;
}> {
  const res = await fetch(`${BACKEND_BASE_URL}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  const body = (await res.json().catch(() => null)) as ApiResponse<{
    account: Record<string, unknown>;
    user_profile: AuthUser;
  }> | null;

  if (!body?.success || !body.data) {
    throw new Error(body?.error?.message || 'Phiên đăng nhập hết hạn');
  }

  return body.data;
}
