// Helper pemanggilan backend ICALORA-LABS.
const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:58010";

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API ${path} gagal: ${res.status}`);
  return res.json() as Promise<T>;
}

export { API_BASE };
