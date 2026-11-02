"use client";

import { useCallback, useEffect, useState } from "react";
import { API_BASE } from "@/lib/api";
import { getFeature } from "@/lib/features";

interface HistoryItem {
  id: number;
  tool: string;
  title: string | null;
  input_preview: string | null;
  created_at: string | null;
}

function fmtDate(iso: string | null): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleString("id-ID", { dateStyle: "medium", timeStyle: "short" });
  } catch {
    return iso;
  }
}

export default function HistoryList({ tool }: { tool?: string }) {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const q = tool ? `?tool=${encodeURIComponent(tool)}` : "";
      const res = await fetch(`${API_BASE}/auth/history${q}`, {
        credentials: "include",
        cache: "no-store",
      });
      if (!res.ok) throw new Error(`${res.status}`);
      const d = await res.json();
      setItems(d.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Gagal memuat.");
    } finally {
      setLoading(false);
    }
  }, [tool]);

  useEffect(() => {
    load();
  }, [load]);

  async function remove(id: number) {
    await fetch(`${API_BASE}/auth/history/${id}`, { method: "DELETE", credentials: "include" });
    setItems((prev) => prev.filter((i) => i.id !== id));
  }

  if (loading) return <p className="text-sm text-neutral-400">Memuat riwayat…</p>;
  if (error) return <p className="text-sm text-rose-500">Gagal memuat: {error}</p>;
  if (items.length === 0)
    return (
      <div className="rounded-xl border border-dashed border-c p-8 text-center text-sm text-neutral-400">
        Belum ada riwayat. Mulai gunakan salah satu layanan.
      </div>
    );

  return (
    <div className="space-y-3">
      {items.map((it) => {
        const f = getFeature(it.tool);
        return (
          <div key={it.id} className="flex items-start gap-3 rounded-xl border border-c surface-2 p-4">
            <div className="text-xl">{f?.icon ?? "📄"}</div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">{it.title ?? f?.name ?? it.tool}</span>
                <span className="rounded-full border border-c px-2 py-0.5 text-[10px] text-neutral-400">
                  {f?.name ?? it.tool}
                </span>
              </div>
              {it.input_preview && (
                <p className="mt-1 line-clamp-2 text-xs text-neutral-500 dark:text-neutral-400">
                  {it.input_preview}
                </p>
              )}
              <div className="mt-1 text-[11px] text-neutral-400">{fmtDate(it.created_at)}</div>
            </div>
            <button
              onClick={() => remove(it.id)}
              className="shrink-0 rounded-lg border border-rose-200 px-2 py-1 text-xs text-rose-600 hover:bg-rose-50 dark:border-rose-900 dark:hover:bg-rose-950"
            >
              Hapus
            </button>
          </div>
        );
      })}
    </div>
  );
}
