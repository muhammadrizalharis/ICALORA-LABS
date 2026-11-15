"use client";

import { API_BASE } from "@/lib/api";

export interface AdminUser {
  id: number;
  email: string | null;
  name: string | null;
  picture: string | null;
  token_balance: number;
  is_demo: boolean;
  is_admin: boolean;
  is_active: boolean;
  created_at: string | null;
  last_login_at: string | null;
}

export interface UserStats {
  total: number;
  admins: number;
  inactive: number;
}

export interface AppSettings {
  maintenance_mode: boolean;
  registration_open: boolean;
  default_token_grant: number;
  feature_flags: Record<string, boolean>;
  feature_slugs: string[];
  rate_limit_enabled: boolean;
  rate_limit_per_min: number;
  token_enforcement: boolean;
  default_tool_cost: number;
  tool_costs: Record<string, number>;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    cache: "no-store",
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = `${res.status}`;
    try {
      const d = await res.json();
      if (d?.detail) detail = typeof d.detail === "string" ? d.detail : detail;
    } catch {
      /* abaikan */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export function listUsers(q = ""): Promise<{ users: AdminUser[]; stats: UserStats }> {
  const qs = q ? `?q=${encodeURIComponent(q)}` : "";
  return req(`/auth/admin/users${qs}`);
}

export function patchUser(
  id: number,
  fields: Partial<Pick<AdminUser, "token_balance" | "is_admin" | "is_active" | "name">>,
): Promise<{ ok: boolean; user: AdminUser }> {
  return req(`/auth/admin/users/${id}`, { method: "PATCH", body: JSON.stringify(fields) });
}

export function deleteUser(id: number): Promise<{ ok: boolean }> {
  return req(`/auth/admin/users/${id}`, { method: "DELETE" });
}

export function resetUserPassword(
  id: number,
): Promise<{ ok: boolean; password: string; email: string | null }> {
  return req(`/auth/admin/users/${id}/reset-password`, { method: "POST" });
}

export interface HistoryItem {
  id: number;
  tool: string;
  title: string | null;
  input_preview: string | null;
  created_at: string | null;
}

export function userHistory(id: number, limit = 50): Promise<{ items: HistoryItem[] }> {
  return req(`/auth/admin/users/${id}/history?limit=${limit}`);
}

export interface AnalyticsOverview {
  days: number;
  totals: {
    runs: number;
    runs_window: number;
    users: number;
    active_users_window: number;
    new_users_window: number;
    tokens_outstanding: number;
  };
  per_tool: { tool: string; count: number }[];
  daily: { day: string; runs: number; users: number }[];
  top_users: { user_id: number | null; email: string | null; name: string | null; runs: number }[];
  jobs: { by_status: Record<string, number>; total: number; error_rate: number };
}

export interface ActivityItem {
  id: number;
  user_id: number | null;
  email: string | null;
  name: string | null;
  tool: string;
  title: string | null;
  input_preview: string | null;
  created_at: string | null;
}

export function getAnalytics(days = 14): Promise<AnalyticsOverview> {
  return req(`/auth/admin/analytics?days=${days}`);
}

export function getActivity(limit = 50, tool?: string): Promise<{ items: ActivityItem[] }> {
  const qs = tool ? `?limit=${limit}&tool=${encodeURIComponent(tool)}` : `?limit=${limit}`;
  return req(`/auth/admin/activity${qs}`);
}

export function getSettings(): Promise<AppSettings> {
  return req(`/auth/admin/settings`);
}

export function putSettings(patch: Partial<AppSettings>): Promise<{ ok: boolean; settings: AppSettings }> {
  return req(`/auth/admin/settings`, { method: "PUT", body: JSON.stringify(patch) });
}

export const FEATURE_LABELS: Record<string, string> = {
  "word-count": "Word Count",
  "extract-text": "Ekstrak Teks",
  "grammar-checker": "Grammar Checker",
  paraphraser: "Paraphraser",
  humanizer: "Humanizer",
  "ai-rewriter": "AI Rewriter",
  "plagiarism-checker": "Plagiarism Checker",
  "ai-chat": "AI Chat",
  "ai-grader": "AI Grader",
  "reader-reactions": "Reader Reactions",
  "resume-builder": "Resume Builder",
  "citation-finder": "Citation Finder",
  "ai-detector": "AI Detector",
  authorship: "Authorship",
  "toc-generator": "Daftar Isi",
  "document-improver": "Perbaikan Dokumen",
  "hidden-text": "Hidden Text",
  "doc-chat": "Doc Chat",
  publikasi: "Rekomendasi Publikasi",
  transcribe: "Transkrip Audio",
  "report-pdf": "Laporan PDF",
};
