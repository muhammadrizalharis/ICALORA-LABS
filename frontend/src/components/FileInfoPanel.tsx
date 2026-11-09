"use client";

import Link from "next/link";
import { useState } from "react";
import { API_BASE } from "@/lib/api";
import { getFeature } from "@/lib/features";
import type { HistoryItemFull } from "@/components/HistoryResultView";

function fmtBytes(n: number | null | undefined): string {
  if (!n || n <= 0) return "—";
  const u = ["B", "KB", "MB", "GB"];
  let i = 0;
  let v = n;
  while (v >= 1024 && i < u.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(v < 10 && i > 0 ? 1 : 0)} ${u[i]}`;
}

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("id-ID", { dateStyle: "long", timeStyle: "short" });
  } catch {
    return iso;
  }
}

function expiryInfo(iso: string | null | undefined): { label: string; expired: boolean } {
  if (!iso) return { label: "—", expired: false };
  const ms = new Date(iso).getTime() - Date.now();
  if (ms <= 0) return { label: "Kedaluwarsa", expired: true };
  const h = Math.floor(ms / 3_600_000);
  if (h >= 24) return { label: `${Math.floor(h / 24)} hari lagi`, expired: false };
  if (h >= 1) return { label: `${h} jam lagi`, expired: false };
  return { label: `${Math.max(1, Math.floor(ms / 60_000))} menit lagi`, expired: false };
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3 py-2">
      <span className="shrink-0 text-xs text-neutral-400">{label}</span>
      <span className="min-w-0 break-words text-right text-xs font-medium text-neutral-700 dark:text-neutral-200">
        {children}
      </span>
    </div>
  );
}

function CopyInline({ text, children }: { text: string; children: React.ReactNode }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => {
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
      className="inline-flex items-center gap-1 font-mono hover:text-[color:var(--brand)]"
      title="Klik untuk menyalin"
    >
      {copied ? "Tersalin!" : children}
    </button>
  );
}

export default function FileInfoPanel({ item }: { item: HistoryItemFull }) {
  const feature = getFeature(item.tool);
  const file = item.file ?? null;
  const exp = expiryInfo(item.expires_at);
  const isPlagiarism = item.tool === "plagiarism-checker";
  const hasFile = !!file?.filename || (isPlagiarism && !!item.result);
  const reportUrl = `${API_BASE}/tools/plagiarism-report/${item.id}`;
  const sha = file?.sha256 ?? null;

  return (
    <aside className="space-y-4 lg:sticky lg:top-6">
      <section className="rounded-xl border border-c surface-2 p-4">
        <h2 className="mb-2 text-sm font-semibold text-neutral-700 dark:text-neutral-200">
          Informasi File
        </h2>
        <div className="divide-y divide-[color:var(--border-c)]">
          <Row label="Report ID">
            <CopyInline text={String(item.id)}>#{item.id}</CopyInline>
          </Row>
          <Row label="Judul">{item.title ?? feature?.name ?? item.tool}</Row>
          <Row label="Jenis alat">{feature?.name ?? item.tool}</Row>
          {file?.filename && <Row label="Nama berkas">{file.filename}</Row>}
          {file?.byte_size != null && <Row label="Ukuran">{fmtBytes(file.byte_size)}</Row>}
          {file?.mime && <Row label="Tipe">{file.mime}</Row>}
          {sha && (
            <Row label="SHA-256">
              <CopyInline text={sha}>{sha.slice(0, 10)}…{sha.slice(-6)}</CopyInline>
            </Row>
          )}
          <Row label="Tanggal">{fmtDate(item.created_at)}</Row>
          <Row label="Status">
            <span
              className="rounded-full px-2 py-0.5 text-[11px] font-semibold"
              style={{
                background: exp.expired
                  ? "color-mix(in srgb, #ef4444 15%, transparent)"
                  : "color-mix(in srgb, var(--brand) 15%, transparent)",
                color: exp.expired ? "#ef4444" : "var(--brand)",
              }}
            >
              {exp.expired ? "Kedaluwarsa" : `Aktif · ${exp.label}`}
            </span>
          </Row>
        </div>
        {!exp.expired && item.retention_days && (
          <p className="mt-2 text-[11px] leading-relaxed text-neutral-400">
            Hasil disimpan maksimal {item.retention_days} hari lalu dihapus otomatis demi
            privasi.
          </p>
        )}
      </section>

      <section className="rounded-xl border border-c surface-2 p-4">
        <h2 className="mb-3 text-sm font-semibold text-neutral-700 dark:text-neutral-200">
          Aksi
        </h2>
        <div className="space-y-2">
          {isPlagiarism && hasFile && (
            <>
              <a
                href={reportUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex w-full items-center justify-center gap-2 rounded-lg bg-[color:var(--brand)] px-4 py-2 text-sm font-medium text-white hover:opacity-90"
              >
                👁️ Lihat (buka PDF)
              </a>
              <a
                href={`${reportUrl}?dl=1`}
                className="flex w-full items-center justify-center gap-2 rounded-lg border border-c surface px-4 py-2 text-sm font-medium text-neutral-700 hover:opacity-80 dark:text-neutral-200"
              >
                ⬇️ Download
              </a>
            </>
          )}
          {feature && (
            <Link
              href={`/dashboard/tools/${item.tool}`}
              className="flex w-full items-center justify-center gap-2 rounded-lg border border-c surface px-4 py-2 text-sm font-medium text-neutral-700 hover:opacity-80 dark:text-neutral-200"
            >
              🔁 Periksa ulang
            </Link>
          )}
          <Link
            href="/dashboard/tools/ai-rewriter"
            className="flex w-full items-center justify-center gap-2 rounded-lg border border-c surface px-4 py-2 text-sm font-medium text-neutral-700 hover:opacity-80 dark:text-neutral-200"
          >
            ✍️ Parafrase ulang
          </Link>
        </div>
      </section>
    </aside>
  );
}
