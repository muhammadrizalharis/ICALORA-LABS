// Helper pemanggilan backend ICALORA-LABS.
// Default: proxy same-origin lewat Next (lihat next.config.ts rewrites),
// sehingga browser cukup mengakses port frontend tanpa CORS.
const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api/backend";

export const BALANCE_EVENT = "icalora:balance";

/** Minta tampilan saldo dimuat ulang (setelah fitur dipakai, gagal, atau job selesai). */
function notifyBalance(path: string, data?: unknown): void {
  if (typeof window === "undefined" || !path.startsWith("/tools/")) return;
  if (data !== undefined) {
    // GET: hanya saat job selesai/gagal (gagal = saldo dikembalikan).
    if (!path.startsWith("/tools/job/")) return;
    const st = (data as { status?: string } | null)?.status;
    if (st !== "done" && st !== "error") return;
  }
  window.dispatchEvent(new Event(BALANCE_EVENT));
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API ${path} gagal: ${res.status}`);
  const data = (await res.json()) as T;
  notifyBalance(path, data);
  return data;
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  notifyBalance(path);
  if (!res.ok) {
    let detail = `${res.status}`;
    try {
      const err = await res.json();
      if (err?.detail) detail = err.detail;
    } catch {
      /* abaikan */
    }
    throw new Error(`API ${path} gagal: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export async function apiUpload<T>(
  path: string,
  file: File,
  fields?: Record<string, string>,
): Promise<T> {
  const form = new FormData();
  form.append("file", file);
  if (fields) {
    for (const [k, v] of Object.entries(fields)) form.append(k, v);
  }
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    body: form,
    cache: "no-store",
  });
  notifyBalance(path);
  if (!res.ok) {
    let detail = `${res.status}`;
    try {
      const err = await res.json();
      if (err?.detail) detail = err.detail;
    } catch {
      /* abaikan */
    }
    throw new Error(`Unggah ${path} gagal: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export { API_BASE };
