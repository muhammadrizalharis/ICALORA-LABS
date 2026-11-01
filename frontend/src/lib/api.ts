// Helper pemanggilan backend ICALORA-LABS.
// Default: proxy same-origin lewat Next (lihat next.config.ts rewrites),
// sehingga browser cukup mengakses port frontend tanpa CORS.
const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api/backend";

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API ${path} gagal: ${res.status}`);
  return res.json() as Promise<T>;
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
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

export async function apiUpload<T>(path: string, file: File): Promise<T> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    body: form,
    cache: "no-store",
  });
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
