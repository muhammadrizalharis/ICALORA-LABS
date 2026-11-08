"use client";

import { useState } from "react";
import { apiPost } from "@/lib/api";
import { escapeHtml } from "@/lib/report";
import ReportBar from "@/components/ReportBar";

export default function ResumeTool() {
  const [info, setInfo] = useState("");
  const [role, setRole] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [out, setOut] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function run() {
    if (!info.trim()) return;
    setLoading(true);
    setError(null);
    setOut(null);
    try {
      const d = await apiPost<{ resume_markdown: string }>("/tools/resume", {
        info,
        target_role: role.trim() || null,
      });
      setOut(d.resume_markdown);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Terjadi kesalahan.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <textarea
        value={info}
        onChange={(e) => setInfo(e.target.value)}
        rows={8}
        placeholder="Masukkan data Anda: nama, kontak, pendidikan, pengalaman, keahlian, dsb. (bebas, satu per baris)"
        className="w-full rounded-lg border border-c surface px-3 py-2 text-sm focus:border-[color:var(--brand)] focus:outline-none"
      />
      <input
        value={role}
        onChange={(e) => setRole(e.target.value)}
        placeholder="Target posisi (opsional) — mis. 'Data Analyst'"
        className="w-full rounded-lg border border-c surface px-3 py-2 text-sm focus:border-[color:var(--brand)] focus:outline-none"
      />
      <button
        onClick={run}
        disabled={loading || !info.trim()}
        className="w-full rounded-xl bg-[color:var(--brand)] px-5 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-40"
      >
        {loading ? "Menyusun…" : "Susun CV"}
      </button>
      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300">
          {error}
        </div>
      )}
      {out !== null && (
        <div className="rounded-xl border border-c surface-2 p-4">
          <div className="mb-2 flex items-center justify-between">
            <div className="text-xs font-medium uppercase tracking-wide text-neutral-400">CV (Markdown)</div>
            <button
              onClick={() => {
                navigator.clipboard.writeText(out);
                setCopied(true);
                setTimeout(() => setCopied(false), 1500);
              }}
              className="text-xs text-[color:var(--brand)] hover:underline"
            >
              {copied ? "Tersalin!" : "Salin"}
            </button>
          </div>
          <pre className="whitespace-pre-wrap font-mono text-xs text-neutral-900 dark:text-neutral-100">{out}</pre>
          <div className="mt-3">
            <ReportBar
              source={info + "\n" + role}
              title="Laporan Penyusunan CV"
              filename="laporan-cv"
              disclaimer="CV disusun otomatis dari data yang Anda masukkan sebagai bahan awal dan sebaiknya disunting kembali sesuai kebutuhan. ID Laporan & hash bersifat reproducible sehingga laporan dapat diverifikasi."
              buildBody={() =>
                `${role ? `<p class="muted">Target posisi: ${escapeHtml(role)}</p>` : ""}` +
                `<h2>CV</h2><div class="doc">${escapeHtml(out)}</div>`
              }
            />
          </div>
        </div>
      )}
    </div>
  );
}
