// Auth context + provider — quản lý trạng thái đăng nhập toàn app.

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  type ReactNode,
} from 'react';

import {
  type AuthUser,
  type AuthData,
  apiLogin,
  apiRegister,
  saveAuth,
  clearAuth,
  getStoredToken,
  getStoredUser,
  getStoredRole,
} from '../services/authApi';

// ── Context shape ────────────────────────────────────────────────────────────

interface AuthState {
  /** Current user (null = chưa đăng nhập) */
  user: AuthUser | null;
  /** JWT access token */
  token: string | null;
  /** Role: "admin" | "user" */
  role: string | null;
  /** Loading state for login/register */
  loading: boolean;
  /** Error message from last action */
  error: string | null;

  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string, name: string) => Promise<void>;
  logout: () => void;
  clearError: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

// ── Provider ─────────────────────────────────────────────────────────────────

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(() => getStoredUser());
  const [token, setToken] = useState<string | null>(() => getStoredToken());
  const [role, setRole] = useState<string | null>(() => getStoredRole());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAuthSuccess = useCallback((data: AuthData) => {
    saveAuth(data);
    setUser(data.user);
    setToken(data.access_token);
    setRole(data.role);
    setError(null);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiLogin(username, password);
      handleAuthSuccess(data);
    } catch (err: any) {
      setError(err.message || 'Đăng nhập thất bại');
      throw err;
    } finally {
      setLoading(false);
    }
  }, [handleAuthSuccess]);

  const register = useCallback(async (username: string, password: string, name: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiRegister(username, password, name);
      handleAuthSuccess(data);
    } catch (err: any) {
      setError(err.message || 'Đăng ký thất bại');
      throw err;
    } finally {
      setLoading(false);
    }
  }, [handleAuthSuccess]);

  const logout = useCallback(() => {
    clearAuth();
    setUser(null);
    setToken(null);
    setRole(null);
    setError(null);
  }, []);

  const clearErrorFn = useCallback(() => setError(null), []);

  return (
    <AuthContext.Provider
      value={{ user, token, role, loading, error, login, register, logout, clearError: clearErrorFn }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// ── Hook ─────────────────────────────────────────────────────────────────────

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within <AuthProvider>');
  }
  return ctx;
}
