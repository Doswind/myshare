// Auth Context - 全局管理 user + token + 权限检查
import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from "react";
import { authApi, type UserInfo } from "@/api/auth";

const TOKEN_KEY = "access_token";
const REFRESH_KEY = "refresh_token";

interface AuthState {
  user: UserInfo | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<UserInfo>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  updateUser: (u: UserInfo) => void;
  hasPermission: (code: string) => boolean;
  isAdmin: boolean;
  permissions: Set<string>;
}

const AuthCtx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(true);

  // 计算权限集合
  const permissions: Set<string> = (() => {
    if (!user) return new Set();
    if (user.is_admin) return new Set(["*"]);
    const codes = new Set<string>();
    for (const r of user.roles) {
      if (!r.is_active) continue;
      for (const p of r.permissions) codes.add(p.code);
    }
    return codes;
  })();

  const isAdmin = user?.is_admin ?? false;

  const hasPermission = useCallback(
    (code: string) => permissions.has("*") || permissions.has(code),
    [permissions]
  );

  // 启动时尝试用 token 拿 /me
  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) {
      setLoading(false);
      return;
    }
    authApi
      .me()
      .then((u) => setUser(u))
      .catch(() => {
        // token 失效，清掉
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(REFRESH_KEY);
      })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const resp = await authApi.login(username, password);
    localStorage.setItem(TOKEN_KEY, resp.access_token);
    localStorage.setItem(REFRESH_KEY, resp.refresh_token);
    setUser(resp.user);
    return resp.user;
  }, []);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      /* noop */
    }
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
    setUser(null);
  }, []);

  const refresh = useCallback(async () => {
    const r = localStorage.getItem(REFRESH_KEY);
    if (!r) throw new Error("no refresh token");
    const resp = await authApi.refresh(r);
    localStorage.setItem(TOKEN_KEY, resp.access_token);
    localStorage.setItem(REFRESH_KEY, resp.refresh_token);
    setUser(resp.user);
  }, []);

  const updateUser = useCallback((u: UserInfo) => setUser(u), []);

  return (
    <AuthCtx.Provider value={{ user, loading, login, logout, refresh, updateUser, hasPermission, isAdmin, permissions }}>
      {children}
    </AuthCtx.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthCtx);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

// 工具：从 localStorage 取 token（给 axios 拦截器用）
export function getAccessToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY);
}

export function clearTokens() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
}
