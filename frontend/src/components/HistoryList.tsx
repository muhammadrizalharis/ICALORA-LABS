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
  const [toolFilter, setToolFilter] = useState<string>("");
  const [query, setQuery] = useState<string>("");

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

  const showFilters = !tool;
  const toolOptions = Array.from(new Set(items.map((i) => i.tool))).sort();
  const q = query.trim().toLowerCase();
  const filtered = items.filter((it) => {
    if (toolFilter && it.tool !== toolFilter) return false;
    if (q) {
      const hay = `${it.title ?? ""} ${it.input_preview ?? ""} ${
        getFeature(it.tool)?.name ?? it.tool
      }`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });

  return (
    <div className="space-y-3">
      {showFilters && (
        <div className="flex flex-col gap-2 sm:flex-row">
          <select
            value={toolFilter}
            onChange={(e) => setToolFilter(e.target.value)}
            className="rounded-lg border border-c surface px-3 py-2 text-sm focus:border-[color:var(--brand)] focus:outline-none"
          >
            <option value="">Semua layanan</option>
            {toolOptions.map((t) => (
              <option key={t} value={t}>
                {getFeature(t)?.name ?? t}
              </option>
            ))}
          </select>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Cari judul atau isi…"
            className="flex-1 rounded-lg border border-c surface px-3 py-2 text-sm focus:border-[color:var(--brand)] focus:outline-none"
          />
          <span className="flex items-center px-1 text-xs text-neutral-400">
            {filtered.length} dari {items.length}
          </span>
        </div>
      )}
      {filtered.length === 0 ? (
        <div className="rounded-xl border border-dashed border-c p-8 text-center text-sm text-neutral-400">
          Tidak ada riwayat yang cocok dengan filter.
        </div>
      ) : (
        filtered.map((it) => {
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
        })
      )}
    </div>
  );
}
