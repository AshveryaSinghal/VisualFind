import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import { AUTH_TOKEN_STORAGE_KEY, AUTH_EXPIRED_EVENT } from "@/api/client";
import * as authService from "@/services/authService";
import type { ProfileUpdatePayload, User } from "@/types";

interface AuthContextValue {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;

  isInitializing: boolean;
  login: (identifier: string, password: string) => Promise<void>;
  signup: (username: string, email: string, password: string, fullName?: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
  updateProfile: (payload: ProfileUpdatePayload) => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [token, setToken] = useState<string | null>(() =>
    window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)
  );
  const [user, setUser] = useState<User | null>(null);
  const [isInitializing, setIsInitializing] = useState<boolean>(true);

  const clearSession = useCallback(() => {
    window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
    setToken(null);
    setUser(null);

    queryClient.clear();
  }, [queryClient]);

  useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      const existingToken = window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
      if (!existingToken) {
        setIsInitializing(false);
        return;
      }
      try {
        const me = await authService.getMe();
        if (!cancelled) setUser(me);
      } catch {
        if (!cancelled) clearSession();
      } finally {
        if (!cancelled) setIsInitializing(false);
      }
    }
    bootstrap();
    return () => {
      cancelled = true;
    };
  }, [clearSession]);

  useEffect(() => {
    const handler = () => clearSession();
    window.addEventListener(AUTH_EXPIRED_EVENT, handler);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, handler);
  }, [clearSession]);

  const login = useCallback(
    async (identifier: string, password: string) => {
      const response = await authService.login(identifier, password);
      window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, response.access_token);
      queryClient.clear();
      setToken(response.access_token);
      setUser(response.user);
    },
    [queryClient]
  );

  const signup = useCallback(
    async (username: string, email: string, password: string, fullName?: string) => {
      const response = await authService.signup(username, email, password, fullName);
      window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, response.access_token);
      queryClient.clear();
      setToken(response.access_token);
      setUser(response.user);
    },
    [queryClient]
  );

  const logout = useCallback(() => {

    authService.logout().catch(() => undefined);
    clearSession();
  }, [clearSession]);

  const refreshUser = useCallback(async () => {
    const me = await authService.getMe();
    setUser(me);
  }, []);

  const updateProfile = useCallback(async (payload: ProfileUpdatePayload) => {
    const updated = await authService.updateProfile(payload);
    setUser(updated);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      token,
      isAuthenticated: Boolean(token && user),
      isInitializing,
      login,
      signup,
      logout,
      refreshUser,
      updateProfile,
    }),
    [user, token, isInitializing, login, signup, logout, refreshUser, updateProfile]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
