"use client";

import { useState } from "react";
import { apiPost } from "@/lib/api";
import { escapeHtml } from "@/lib/report";
import ReportBar from "@/components/ReportBar";
import TextInput from "@/components/TextInput";

interface ImproveResult {
  improved: string;
  goal: string | null;
}

const GOALS = ["", "lebih ringkas", "lebih formal/baku", "lebih jelas & runtut", "gaya akademik"];

export default function ImproveTool() {
  const [text, setText] = useState("");
  const [goal, setGoal] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [res, setRes] = useState<ImproveResult | null>(null);
  const [copied, setCopied] = useState(false);

  async function run() {
    if (!text.trim()) return;
    setLoading(true);
    setError(null);
    setRes(null);
    try {
      setRes(await apiPost<ImproveResult>("/tools/improve", { text, goal: goal || null }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Terjadi kesalahan.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <TextInput
        value={text}
        onChange={setText}
        rows={8}
        placeholder="Tempel dokumen (atau unggah PDF/DOCX) yang ingin diperbaiki…"
      />
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-neutral-500 dark:text-neutral-400">Fokus:</span>
        {GOALS.map((g) => (
          <button
            key={g}
            onClick={() => setGoal(g)}
            className={`rounded-full border px-3 py-1 text-xs transition ${
              goal === g
                ? "border-[color:var(--brand)] bg-[color:var(--brand)] text-white"
                : "border-c text-neutral-600 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-900"
            }`}
          >
            {g || "otomatis"}
          </button>
        ))}
      </div>
      <button
        onClick={run}
        disabled={loading || !text.trim()}
        className="w-full rounded-xl bg-[color:var(--brand)] px-5 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-40"
      >
        {loading ? "Memperbaiki…" : "Perbaiki Dokumen"}
      </button>
      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300">
          {error}
        </div>
      )}
      {res && (
        <div className="space-y-2">
          <div className="whitespace-pre-wrap rounded-xl border border-c surface-2 p-4 text-sm text-neutral-800 dark:text-neutral-200">
            {res.improved}
          </div>
          <button
            onClick={() => {
              navigator.clipboard.writeText(res.improved);
              setCopied(true);
              setTimeout(() => setCopied(false), 1500);
            }}
            className="rounded-lg border border-c px-4 py-1.5 text-xs text-neutral-600 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-900"
          >
            {copied ? "Tersalin ✓" : "Salin Hasil"}
          </button>
          <ReportBar
            source={text}
            title="Laporan Perbaikan Dokumen"
            filename="laporan-perbaikan-dokumen"
            disclaimer="Hasil perbaikan dihasilkan otomatis sebagai bahan bantu penyuntingan dan sebaiknya ditinjau kembali oleh penulis. ID Laporan & hash bersifat reproducible sehingga laporan dapat diverifikasi."
            buildBody={() =>
              `${res.goal ? `<p class="muted">Fokus perbaikan: ${escapeHtml(res.goal)}</p>` : ""}` +
              `<h2>Dokumen Hasil Perbaikan</h2><div class="doc">${escapeHtml(res.improved)}</div>`
            }
          />
        </div>
      )}
    </div>
  );
}
