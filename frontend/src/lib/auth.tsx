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
  is_admin: boolean;
}

interface ResetPasswordResult {
  password: string;
  email: string | null;
  emailed: boolean;
  email_error: string | null;
}

interface AuthState {
  loading: boolean;
  user: User | null;
  googleEnabled: boolean;
  adminEnabled: boolean;
  emailEnabled: boolean;
  historyRetentionDays: number;
  refresh: () => Promise<void>;
  adminLogin: (password: string) => Promise<boolean>;
  changeAdminPassword: (currentPassword: string, newPassword: string) => Promise<string | null>;
  passwordLogin: (email: string, password: string) => Promise<string | null>;
  resetPassword: () => Promise<ResetPasswordResult | null>;
  logout: () => Promise<void>;
}

const AuthCtx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<User | null>(null);
  const [googleEnabled, setGoogleEnabled] = useState(false);
  const [adminEnabled, setAdminEnabled] = useState(false);
  const [emailEnabled, setEmailEnabled] = useState(false);
  const [historyRetentionDays, setHistoryRetentionDays] = useState(3);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/auth/me`, { credentials: "include", cache: "no-store" });
      const d = await res.json();
      setUser(d.user);
      setGoogleEnabled(d.google_enabled);
      setAdminEnabled(d.admin_enabled);
      setEmailEnabled(Boolean(d.email_enabled));
      if (typeof d.history_retention_days === "number")
        setHistoryRetentionDays(d.history_retention_days);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const adminLogin = useCallback(
    async (password: string): Promise<boolean> => {
      const res = await fetch(`${API_BASE}/auth/admin-login`, {
        method: "POST",
        credentials: "include",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ password }),
      });
      if (!res.ok) return false;
      await refresh();
      return true;
    },
    [refresh],
  );

  const changeAdminPassword = useCallback(
    async (currentPassword: string, newPassword: string): Promise<string | null> => {
      const res = await fetch(`${API_BASE}/auth/admin-password`, {
        method: "POST",
        credentials: "include",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      });
      if (res.ok) return null;
      try {
        const d = await res.json();
        return typeof d?.detail === "string" ? d.detail : "Gagal mengubah kata sandi.";
      } catch {
        return "Gagal mengubah kata sandi.";
      }
    },
    [],
  );

  const passwordLogin = useCallback(
    async (email: string, password: string): Promise<string | null> => {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        credentials: "include",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (res.ok) {
        await refresh();
        return null;
      }
      try {
        const d = await res.json();
        return typeof d?.detail === "string" ? d.detail : "Gagal masuk.";
      } catch {
        return "Gagal masuk.";
      }
    },
    [refresh],
  );

  const resetPassword = useCallback(async (): Promise<ResetPasswordResult | null> => {
    const res = await fetch(`${API_BASE}/auth/reset-password`, {
      method: "POST",
      credentials: "include",
    });
    if (!res.ok) return null;
    const d = await res.json();
    return {
      password: d.password,
      email: d.email ?? null,
      emailed: Boolean(d.emailed),
      email_error: d.email_error ?? null,
    };
  }, []);

  const logout = useCallback(async () => {
    await fetch(`${API_BASE}/auth/logout`, { method: "POST", credentials: "include" });
    setUser(null);
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <AuthCtx.Provider
      value={{ loading, user, googleEnabled, adminEnabled, emailEnabled, historyRetentionDays, refresh, adminLogin, changeAdminPassword, passwordLogin, resetPassword, logout }}
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
