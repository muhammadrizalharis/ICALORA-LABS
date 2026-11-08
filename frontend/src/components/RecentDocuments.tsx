"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { API_BASE } from "@/lib/api";
import { getFeature } from "@/lib/features";
import { useAuth } from "@/lib/auth";

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

export default function RecentDocuments({ limit = 6 }: { limit?: number }) {
  const { historyRetentionDays } = useAuth();
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/auth/history?limit=${limit}`, {
          credentials: "include",
          cache: "no-store",
        });
        if (!res.ok) throw new Error();
        const d = await res.json();
        if (alive) setItems(d.items);
      } catch {
        if (alive) setItems([]);
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [limit]);

  return (
    <div>
      <div className="mb-2 flex items-end justify-between">
        <h2 className="text-lg font-semibold">Dokumen terakhir</h2>
        <Link href="/dashboard/history" className="text-xs text-[color:var(--brand)] hover:underline">
          Lihat semua riwayat →
        </Link>
      </div>
      <p className="mb-4 text-xs text-neutral-400">
        Hasil tersimpan maksimal {historyRetentionDays} hari, lalu dihapus otomatis dari server.
      </p>

      {loading ? (
        <p className="text-sm text-neutral-400">Memuat…</p>
      ) : items.length === 0 ? (
        <div className="rounded-xl border border-dashed border-c p-8 text-center text-sm text-neutral-400">
          Belum ada dokumen. Mulai gunakan salah satu layanan di bawah.
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((it) => {
            const f = getFeature(it.tool);
            return (
              <Link
                key={it.id}
                href={`/dashboard/history/view/${it.id}`}
                className="flex items-center gap-3 rounded-xl border border-c surface-2 px-4 py-3 transition hover:border-[color:var(--brand)]"
              >
                <span className="inline-flex items-center gap-1.5 rounded-lg bg-[color:var(--brand-soft)] px-2.5 py-1 text-xs font-medium text-[color:var(--brand)]">
                  <span>{f?.icon ?? "📄"}</span>
                  {f?.name ?? it.tool}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium text-neutral-900 dark:text-neutral-100">
                    {it.title ?? f?.name ?? it.tool}
                  </div>
                  {it.input_preview && (
                    <div className="truncate text-xs text-neutral-400">{it.input_preview}</div>
                  )}
                </div>
                <div className="hidden shrink-0 text-xs text-neutral-400 sm:block">
                  {fmtDate(it.created_at)}
                </div>
                <span className="shrink-0 rounded-full bg-emerald-500/15 px-2 py-0.5 text-[11px] font-medium text-emerald-600 dark:text-emerald-400">
                  Selesai
                </span>
                <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full border border-c text-neutral-400">
                  👁
                </span>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
