"use client";

import { useEffect, useState } from "react";
import { reportMeta, reportShell, type ReportMeta } from "@/lib/report";
import { downloadPdfReport } from "@/lib/download";

interface ReportBarProps {
  /** Teks sumber untuk menghasilkan ID & hash yang dapat diverifikasi. */
  source: string;
  /** Judul laporan, mis. "Laporan Perbaikan Dokumen". */
  title: string;
  /** Nama berkas unduhan (tanpa ekstensi diperbolehkan). */
  filename: string;
  /** Pembangun isi laporan (HTML). Dipanggil saat tombol unduh ditekan. */
  buildBody: () => string;
  disclaimer?: string;
}

/**
 * Bilah kredibilitas + unduh laporan, seragam di semua fitur:
 * menampilkan ID Laporan terverifikasi, hash SHA-256, waktu, dan tombol PDF.
 */
export default function ReportBar({
  source,
  title,
  filename,
  buildBody,
  disclaimer,
}: ReportBarProps) {
  const [meta, setMeta] = useState<ReportMeta | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    reportMeta(source).then((m) => {
      if (alive) setMeta(m);
    });
    return () => {
      alive = false;
    };
  }, [source]);

  async function onDownload() {
    if (busy) return;
    setBusy(true);
    try {
      const m = meta ?? (await reportMeta(source));
      const html = reportShell({ title, bodyHtml: buildBody(), meta: m, disclaimer });
      await downloadPdfReport(filename, html);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-c bg-neutral-50 px-4 py-3 text-[11px] text-neutral-500 dark:bg-white/5 dark:text-neutral-400">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <span>
          🆔 ID Laporan:{" "}
          <span className="font-mono font-semibold text-neutral-700 dark:text-neutral-200">
            {meta?.reportId ?? "…"}
          </span>
        </span>
        {meta && (
          <span>
            🔒 SHA-256: <span className="font-mono">{meta.hash.slice(0, 16)}…</span>
          </span>
        )}
      </div>
      <button
        onClick={onDownload}
        disabled={busy}
        className="rounded-lg border border-c bg-white px-3 py-1.5 text-xs font-medium text-neutral-700 hover:bg-neutral-100 disabled:opacity-50 dark:bg-white/5 dark:text-neutral-200 dark:hover:bg-white/10"
      >
        {busy ? "Menyiapkan…" : "⬇ Unduh Laporan (PDF)"}
      </button>
    </div>
  );
}
