"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { API_BASE } from "@/lib/api";
import HistoryResultView, { HistoryItemFull } from "@/components/HistoryResultView";

export default function HistoryViewPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [item, setItem] = useState<HistoryItemFull | null>(null);
  const [loading, setLoading] = useState(true);
  const [expired, setExpired] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/auth/history/${id}`, {
          credentials: "include",
          cache: "no-store",
        });
        if (!alive) return;
        if (res.status === 404) {
          setExpired(true);
          return;
        }
        if (!res.ok) throw new Error(`${res.status}`);
        const d = await res.json();
        if (alive) setItem(d);
      } catch (e) {
        if (alive) setError(e instanceof Error ? e.message : "Gagal memuat.");
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [id]);

  return (
    <div className="mx-auto max-w-4xl p-8">
      <Link href="/dashboard" className="text-xs text-neutral-400 hover:underline">
        ← Beranda
      </Link>
      <div className="mt-4">
        {loading && <p className="text-sm text-neutral-400">Memuat hasil…</p>}
        {!loading && error && (
          <p className="text-sm text-rose-500">Gagal memuat: {error}</p>
        )}
        {!loading && expired && (
          <div className="rounded-xl border border-dashed border-c surface-2 p-8 text-center">
            <div className="text-3xl">🗂️</div>
            <h1 className="mt-3 text-lg font-semibold text-neutral-800 dark:text-neutral-100">
              File hasil sudah melewati masa simpan
            </h1>
            <p className="mx-auto mt-2 max-w-md text-sm text-neutral-500 dark:text-neutral-400">
              Demi privasi, hasil hanya disimpan maksimal 3 hari lalu dihapus otomatis dari
              server. Silakan jalankan pemeriksaan ulang untuk mendapatkan hasil terbaru.
            </p>
            <Link
              href="/dashboard"
              className="mt-4 inline-block rounded-lg bg-[color:var(--brand)] px-4 py-2 text-sm font-medium text-white hover:opacity-90"
            >
              Kembali ke Beranda
            </Link>
          </div>
        )}
        {!loading && item && <HistoryResultView item={item} />}
      </div>
    </div>
  );
}
