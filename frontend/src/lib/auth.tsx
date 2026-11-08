"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { API_BASE } from "@/lib/api";

export interface User {
  id: number;
  email: string | null;
  name: string | null;
  picture: string | null;
  token_balance: number;
  is_demo: boolean;
}

interface AuthState {
  loading: boolean;
  user: User | null;
  googleEnabled: boolean;
  demoEnabled: boolean;
  historyRetentionDays: number;
  refresh: () => Promise<void>;
  demoLogin: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthCtx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<User | null>(null);
  const [googleEnabled, setGoogleEnabled] = useState(false);
  const [demoEnabled, setDemoEnabled] = useState(false);
  const [historyRetentionDays, setHistoryRetentionDays] = useState(3);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/auth/me`, { credentials: "include", cache: "no-store" });
      const d = await res.json();
      setUser(d.user);
      setGoogleEnabled(d.google_enabled);
      setDemoEnabled(d.demo_enabled);
      if (typeof d.history_retention_days === "number")
        setHistoryRetentionDays(d.history_retention_days);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const demoLogin = useCallback(async () => {
    await fetch(`${API_BASE}/auth/demo-login`, {
      method: "POST",
      credentials: "include",
    });
    await refresh();
  }, [refresh]);

  const logout = useCallback(async () => {
    await fetch(`${API_BASE}/auth/logout`, { method: "POST", credentials: "include" });
    setUser(null);
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <AuthCtx.Provider
      value={{ loading, user, googleEnabled, demoEnabled, historyRetentionDays, refresh, demoLogin, logout }}
    >
      {children}
    </AuthCtx.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthCtx);
  if (!ctx) throw new Error("useAuth harus di dalam AuthProvider");
  return ctx;
}

export function googleLoginUrl(): string {
  return `${API_BASE}/auth/google/login`;
}
