"use client";

import { useState } from "react";
import { apiPost } from "@/lib/api";
import { escapeHtml } from "@/lib/report";
import ReportBar from "@/components/ReportBar";
import TextInput from "@/components/TextInput";

interface WritingMetrics {
  characters: number;
  words: number;
  sentences: number;
  reading_time_min: number;
  speaking_time_min: number;
}
interface WritingIssue {
  category: string;
  severity: "critical" | "advanced";
  original: string;
  suggestion: string;
  explanation: string;
}
interface WritingReport {
  corrected: string;
  metrics: WritingMetrics;
  score: number;
  better_than_percent: number;
  issues: WritingIssue[];
  issue_summary: { total: number; critical: number; advanced: number };
}

const CATEGORY_TONE: Record<string, string> = {
  Ketepatan: "border-rose-300 text-rose-600 dark:text-rose-400",
  Kejelasan: "border-sky-300 text-sky-600 dark:text-sky-400",
  Keterlibatan: "border-violet-300 text-violet-600 dark:text-violet-400",
  Penyampaian: "border-emerald-300 text-emerald-600 dark:text-emerald-400",
};

function scoreTone(v: number): string {
  if (v >= 80) return "border-emerald-400 text-emerald-600";
  if (v >= 55) return "border-amber-400 text-amber-600";
  return "border-rose-400 text-rose-600";
}

function fmtMin(v: number): string {
  if (v < 1) return `${Math.round(v * 60)} dtk`;
  return `${v} mnt`;
}

export default function WritingReportTool() {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [res, setRes] = useState<WritingReport | null>(null);
  const [copied, setCopied] = useState(false);

  async function run() {
    if (!text.trim()) return;
    setLoading(true);
    setError(null);
    setRes(null);
    try {
      setRes(await apiPost<WritingReport>("/tools/grammar-check", { text }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Terjadi kesalahan.");
    } finally {
      setLoading(false);
    }
  }

  function copyCorrected() {
    if (!res) return;
    navigator.clipboard.writeText(res.corrected);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  function buildReportBody(): string {
    if (!res) return "";
    const m = res.metrics;
    const metricRows = [
      ["Karakter", m.characters],
      ["Kata", m.words],
      ["Kalimat", m.sentences],
      ["Waktu baca", fmtMin(m.reading_time_min)],
      ["Waktu bicara", fmtMin(m.speaking_time_min)],
    ]
      .map(
        ([l, v]) =>
          `<tr><td>${escapeHtml(String(l))}</td><td class="r">${escapeHtml(String(v))}</td></tr>`,
      )
      .join("");
    const issuesHtml = res.issues.length
      ? res.issues
          .map(
            (i) =>
              `<div style="margin:10px 0"><span class="pill ${
                i.severity === "critical" ? "pill-bad" : "pill-warn"
              }">${i.severity === "critical" ? "Kritis" : "Lanjutan"}</span>` +
              `<span class="pill">${escapeHtml(i.category)}</span><br>` +
              `<span class="muted">Asli:</span> ${escapeHtml(i.original)}<br>` +
              `<span class="muted">Saran:</span> <b>${escapeHtml(i.suggestion)}</b>` +
              (i.explanation ? `<br><span class="muted">${escapeHtml(i.explanation)}</span>` : "") +
              `</div>`,
          )
          .join("")
      : `<p class="muted">Tidak ada masalah penulisan yang signifikan terdeteksi.</p>`;
    return (
      `<div class="summary">Skor Penulisan: ${res.score}/100 · lebih baik dari ${res.better_than_percent}% teks</div>` +
      `<h2>Metrik</h2><table>${metricRows}</table>` +
      `<h2>Masalah Penulisan (${res.issue_summary.total} · ${res.issue_summary.critical} kritis / ${res.issue_summary.advanced} lanjutan)</h2>${issuesHtml}` +
      `<h2>Teks Hasil Perbaikan</h2><div class="doc">${escapeHtml(res.corrected)}</div>`
    );
  }

  const m = res?.metrics;

  return (
    <div className="space-y-4">
      <TextInput
        value={text}
        onChange={setText}
        rows={8}
        placeholder="Tempel teks untuk diperiksa tata bahasa & kualitas penulisannya…"
      />
      <button
        onClick={run}
        disabled={loading || !text.trim()}
        className="w-full rounded-xl bg-[color:var(--brand)] px-5 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-40"
      >
        {loading ? "Memeriksa…" : "Periksa Tata Bahasa"}
      </button>

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300">
          {error}
        </div>
      )}

      {res && m && (
        <div className="space-y-5 rounded-xl border border-c p-5">
          <div className="flex flex-wrap items-center gap-8">
            <div className="flex flex-col items-center">
              <div
                className={`flex h-24 w-24 items-center justify-center rounded-full border-4 text-2xl font-bold ${scoreTone(
                  res.score,
                )}`}
              >
                {res.score}
              </div>
              <div className="mt-2 text-center text-xs font-medium text-neutral-500 dark:text-neutral-400">
                Skor Penulisan
              </div>
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm text-neutral-600 dark:text-neutral-300">
                Lebih baik dari{" "}
                <span className="font-semibold text-neutral-900 dark:text-neutral-100">
                  {res.better_than_percent}%
                </span>{" "}
                teks yang dianalisis.
              </p>
              <div className="mt-3 flex flex-wrap gap-2 text-xs">
                <span className="rounded-full border border-c px-3 py-1 text-neutral-600 dark:text-neutral-300">
                  {m.characters.toLocaleString("id-ID")} karakter
                </span>
                <span className="rounded-full border border-c px-3 py-1 text-neutral-600 dark:text-neutral-300">
                  {m.words.toLocaleString("id-ID")} kata
                </span>
                <span className="rounded-full border border-c px-3 py-1 text-neutral-600 dark:text-neutral-300">
                  {m.sentences.toLocaleString("id-ID")} kalimat
                </span>
                <span className="rounded-full border border-c px-3 py-1 text-neutral-600 dark:text-neutral-300">
                  📖 {fmtMin(m.reading_time_min)} baca
                </span>
                <span className="rounded-full border border-c px-3 py-1 text-neutral-600 dark:text-neutral-300">
                  🗣 {fmtMin(m.speaking_time_min)} bicara
                </span>
              </div>
              <div className="mt-3 flex flex-wrap gap-2 text-xs">
                <span className="rounded-full bg-neutral-100 px-3 py-1 font-medium text-neutral-700 dark:bg-white/10 dark:text-neutral-200">
                  {res.issue_summary.total} masalah
                </span>
                <span className="rounded-full bg-rose-100 px-3 py-1 font-medium text-rose-700 dark:bg-rose-950 dark:text-rose-300">
                  {res.issue_summary.critical} kritis
                </span>
                <span className="rounded-full bg-amber-100 px-3 py-1 font-medium text-amber-700 dark:bg-amber-950 dark:text-amber-300">
                  {res.issue_summary.advanced} lanjutan
                </span>
              </div>
            </div>
          </div>

          {res.issues.length > 0 && (
            <div>
              <div className="mb-2 text-sm font-semibold text-neutral-800 dark:text-neutral-200">
                Masalah Penulisan
              </div>
              <ul className="space-y-2">
                {res.issues.map((i, idx) => (
                  <li key={idx} className="rounded-lg border border-c surface-2 p-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${
                          CATEGORY_TONE[i.category] ?? "border-c text-neutral-500"
                        }`}
                      >
                        {i.category}
                      </span>
                      <span
                        className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                          i.severity === "critical"
                            ? "bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300"
                            : "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300"
                        }`}
                      >
                        {i.severity === "critical" ? "Kritis" : "Lanjutan"}
                      </span>
                    </div>
                    <p className="mt-2 text-xs text-neutral-500 line-through dark:text-neutral-400">
                      {i.original}
                    </p>
                    <p className="text-xs font-medium text-neutral-900 dark:text-neutral-100">
                      {i.suggestion}
                    </p>
                    {i.explanation && (
                      <p className="mt-1 text-[11px] text-neutral-400">{i.explanation}</p>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div>
            <div className="mb-2 flex items-center justify-between">
              <span className="text-sm font-semibold text-neutral-800 dark:text-neutral-200">
                Teks Hasil Perbaikan
              </span>
              <button
                onClick={copyCorrected}
                className="text-xs text-[color:var(--brand)] hover:underline"
              >
                {copied ? "Tersalin!" : "Salin"}
              </button>
            </div>
            <div className="whitespace-pre-wrap rounded-lg border border-c bg-white p-4 text-sm leading-relaxed text-neutral-800 dark:bg-neutral-900 dark:text-neutral-100">
              {res.corrected}
            </div>
          </div>

          <ReportBar
            source={text}
            title="Laporan Penulisan (Writing Report)"
            filename="laporan-penulisan"
            disclaimer="Laporan penulisan dihasilkan otomatis sebagai bahan bantu akademik; tinjau setiap saran bersama konteks karya. ID Laporan & hash bersifat reproducible sehingga laporan dapat diverifikasi."
            buildBody={buildReportBody}
          />
        </div>
      )}
    </div>
  );
}
