"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { API_BASE } from "@/lib/api";
import { getFeature } from "@/lib/features";
import { useAuth } from "@/lib/auth";
import { useJobs, useHistoryVersion } from "@/lib/useJobs";
import { dismissJob, type Job } from "@/lib/jobs";
import NewDocumentMenu from "@/components/NewDocumentMenu";

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

function StatusBadge({ status }: { status: "processing" | "done" | "error" }) {
  if (status === "processing")
    return (
      <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-amber-500/15 px-2 py-0.5 text-[11px] font-medium text-amber-600 dark:text-amber-400">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-amber-500" />
        Sedang diproses
      </span>
    );
  if (status === "error")
    return (
      <span className="shrink-0 rounded-full bg-rose-500/15 px-2 py-0.5 text-[11px] font-medium text-rose-600 dark:text-rose-400">
        Gagal
      </span>
    );
  return (
    <span className="shrink-0 rounded-full bg-emerald-500/15 px-2 py-0.5 text-[11px] font-medium text-emerald-600 dark:text-emerald-400">
      Selesai
    </span>
  );
}

function JobRow({ job }: { job: Job }) {
  const f = getFeature(job.tool);
  const body = (
    <>
      <span className="inline-flex items-center gap-1.5 rounded-lg bg-[color:var(--brand-soft)] px-2.5 py-1 text-xs font-medium text-[color:var(--brand)]">
        <span>{f?.icon ?? "📄"}</span>
        {f?.name ?? job.tool}
      </span>
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium text-neutral-900 dark:text-neutral-100">
          {job.title}
        </div>
        <div className="truncate text-xs text-neutral-400">
          {job.status === "processing"
            ? "Dokumen sedang diperiksa di server…"
            : job.status === "error"
              ? job.error ?? "Terjadi kesalahan."
              : "Pemeriksaan selesai."}
        </div>
      </div>
      <StatusBadge status={job.status} />
    </>
  );

  if (job.status === "done" && job.historyId) {
    return (
      <Link
        href={`/dashboard/history/view/${job.historyId}`}
        className="flex items-center gap-3 rounded-xl border border-emerald-300/50 surface-2 px-4 py-3 transition hover:border-[color:var(--brand)]"
      >
        {body}
      </Link>
    );
  }
  return (
    <div className="flex items-center gap-3 rounded-xl border border-c surface-2 px-4 py-3">
      {body}
      {job.status === "error" && (
        <button
          onClick={() => dismissJob(job.tempId)}
          className="shrink-0 text-xs text-neutral-400 hover:text-rose-500"
          title="Tutup"
        >
          ✕
        </button>
      )}
    </div>
  );
}

export default function RecentDocuments({ limit = 6 }: { limit?: number }) {
  const { historyRetentionDays } = useAuth();
  const jobs = useJobs();
  const historyVersion = useHistoryVersion();
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");

  // Ambil lebih banyak dari yang ditampilkan agar pencarian mencakup riwayat
  // yang lebih luas, bukan hanya beberapa dokumen terakhir.
  const fetchLimit = Math.max(limit, 50);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/auth/history?limit=${fetchLimit}`, {
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
  }, [fetchLimit, historyVersion]);

  const q = query.trim().toLowerCase();

  function matchesQuery(tool: string, title: string | null, preview: string | null): boolean {
    if (!q) return true;
    const f = getFeature(tool);
    return [title, preview, f?.name, tool].some((s) => (s ?? "").toLowerCase().includes(q));
  }

  // Jangan tampilkan dobel: sembunyikan riwayat yang sudah diwakili kartu job "selesai".
  const doneJobIds = new Set(
    jobs.filter((j) => j.status === "done" && j.historyId).map((j) => j.historyId),
  );
  const visibleJobs = jobs.filter((j) => matchesQuery(j.tool, j.title, null));
  const filteredItems = items.filter(
    (it) => !doneJobIds.has(it.id) && matchesQuery(it.tool, it.title, it.input_preview),
  );
  // Tanpa pencarian: batasi ke `limit` dokumen terakhir. Saat mencari: tampilkan
  // semua yang cocok dari kumpulan yang diambil.
  const visibleItems = q ? filteredItems : filteredItems.slice(0, limit);

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-end justify-between gap-2">
        <h2 className="text-lg font-semibold">Dokumen terakhir</h2>
        <Link href="/dashboard/history" className="text-xs text-[color:var(--brand)] hover:underline">
          Lihat semua riwayat →
        </Link>
      </div>
      <p className="mb-3 text-xs text-neutral-400">
        Hasil tersimpan maksimal {historyRetentionDays} hari, lalu dihapus otomatis dari server.
      </p>

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative min-w-0 flex-1">
          <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm text-neutral-400">
            🔍
          </span>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Cari dokumen berdasarkan judul, isi, atau tool…"
            className="w-full rounded-lg border border-c surface py-2 pl-9 pr-3 text-sm outline-none focus:border-[color:var(--brand)]"
          />
          {query && (
            <button
              onClick={() => setQuery("")}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-xs text-neutral-400 hover:text-neutral-600"
              aria-label="Bersihkan pencarian"
            >
              ✕
            </button>
          )}
        </div>
        <NewDocumentMenu />
      </div>

      {loading && jobs.length === 0 ? (
        <p className="text-sm text-neutral-400">Memuat…</p>
      ) : visibleJobs.length === 0 && visibleItems.length === 0 ? (
        <div className="rounded-xl border border-dashed border-c p-8 text-center text-sm text-neutral-400">
          {q
            ? "Tidak ada dokumen yang cocok dengan pencarian."
            : "Belum ada dokumen. Klik “Tambah baru” untuk mulai memeriksa."}
        </div>
      ) : (
        <div className="space-y-2">
          {visibleJobs.map((j) => (
            <JobRow key={j.tempId} job={j} />
          ))}
          {visibleItems.map((it) => {
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
                <StatusBadge status="done" />
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
