"use client";

import { useState } from "react";
import { downloadPdfReport } from "@/lib/download";
import { API_BASE, apiPost } from "@/lib/api";
import {
  HILITE,
  MIN_WORDS,
  MIN_PCT,
  MATCH_GROUP_META,
  MATCH_GROUP_ORDER,
  escHtml,
  buildHighlight,
  buildReportHtml,
  verdictFor,
  toneForScore,
  type Report,
  type MatchedPassage,
} from "@/lib/plagiarismReport";

function ScoreRing({ value, label, tone }: { value: number; label: string; tone: string }) {
  const display = value > 0 && value < 1 ? "<1" : value < 10 ? value.toFixed(1) : value.toFixed(0);
  return (
    <div className="flex flex-col items-center">
      <div
        className={`flex h-24 w-24 items-center justify-center rounded-full border-4 text-2xl font-bold ${tone}`}
      >
        {display}%
      </div>
      <div className="mt-2 text-center text-xs font-medium text-neutral-500 dark:text-neutral-400">
        {label}
      </div>
    </div>
  );
}

interface OnlineSource {
  title: string | null;
  doi: string | null;
  url: string | null;
  source: string | null;
  matches: number;
}
interface OnlineResult {
  integrity_index: number;
  matched_sentences: number;
  total_sentences: number;
  queried_sentences: number;
  candidates_checked: number;
  providers: { name: string; hits: number }[];
  sources: OnlineSource[];
  matched_passages: MatchedPassage[];
  coverage_note?: string;
}

interface Props {
  report: Report;
  /** Teks dokumen asli untuk sorotan. Default: report.document_text. */
  documentText?: string;
  docTitle?: string;
  /** ID riwayat; bila ada + has_original_pdf, aktifkan laporan berformat identik. */
  historyId?: number;
}

/** Laporan kemiripan interaktif — dipakai di halaman tool & penampil riwayat. */
export default function PlagiarismReport({ report, documentText, docTitle = "", historyId }: Props) {
  const [exShort, setExShort] = useState(false);
  const [exSmall, setExSmall] = useState(false);
  const [exQuotes, setExQuotes] = useState(false);
  const [exBib, setExBib] = useState(false);
  const [busy, setBusy] = useState(false);

  // Cek sumber daring (tanpa unduh) — lapis pelengkap opsional.
  const [onlineBusy, setOnlineBusy] = useState(false);
  const [onlineErr, setOnlineErr] = useState<string | null>(null);
  const [online, setOnline] = useState<OnlineResult | null>(null);

  async function runOnline() {
    if (onlineBusy || !text.trim()) return;
    setOnlineBusy(true);
    setOnlineErr(null);
    try {
      const res = await apiPost<OnlineResult>("/tools/plagiarism-online", { text });
      setOnline(res);
    } catch (e) {
      setOnlineErr(e instanceof Error ? e.message : "Cek daring gagal.");
    } finally {
      setOnlineBusy(false);
    }
  }

  const text = documentText ?? report.document_text ?? "";

  function activePassages(): MatchedPassage[] {
    return report.matched_passages.filter(
      (p) => !(exQuotes && p.quoted) && !(exBib && p.in_bibliography),
    );
  }

  function hiOpts(): { minWords: number; exclude: Set<string> } {
    let exclude = new Set<string>();
    if (exSmall) {
      const base = buildHighlight(text, activePassages(), report.char_count);
      exclude = new Set(base.sources.filter((s) => s.pct < MIN_PCT).map((s) => s.key));
    }
    return { minWords: exShort ? MIN_WORDS : 0, exclude };
  }

  function reportHtml(): string {
    return buildReportHtml({
      report,
      text,
      docTitle,
      passages: activePassages(),
      hiOpts: hiOpts(),
    });
  }

  async function downloadReport() {
    if (busy) return;
    setBusy(true);
    try {
      await downloadPdfReport(`laporan-kemiripan-${report.report_id ?? Date.now()}.pdf`, reportHtml());
    } finally {
      setBusy(false);
    }
  }

  async function viewReport() {
    if (busy) return;
    setBusy(true);
    try {
      const html = reportHtml();
      const res = await fetch(`${API_BASE}/tools/report-pdf`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ html, filename: "laporan-kemiripan.pdf" }),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      const url = URL.createObjectURL(await res.blob());
      window.open(url, "_blank", "noopener");
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch {
      // Fallback: buka versi HTML laporan di tab baru.
      const url = URL.createObjectURL(new Blob([reportHtml()], { type: "text/html;charset=utf-8" }));
      window.open(url, "_blank", "noopener");
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } finally {
      setBusy(false);
    }
  }

  const hi = buildHighlight(text, activePassages(), report.char_count, false, hiOpts());
  const filtersActive = exShort || exSmall || exQuotes || exBib;
  const headlineIndex = report.integrity_index ?? report.overall_similarity;
  const shownIndex = filtersActive
    ? Math.min(100, Math.round(hi.sources.reduce((a, s) => a + s.pct, 0) * 10) / 10)
    : headlineIndex;

  const hasOriginal = Boolean(report.has_original_pdf && historyId);
  const originalReportUrl = (dl: boolean) =>
    `${API_BASE}/tools/plagiarism-report/${historyId}${dl ? "?dl=1" : ""}`;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2">
        {hasOriginal ? (
          <>
            <a
              href={originalReportUrl(false)}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-lg bg-[color:var(--brand)] px-4 py-2 text-xs font-semibold text-white hover:opacity-90"
            >
              👁 Lihat Laporan (format asli)
            </a>
            <a
              href={originalReportUrl(true)}
              className="rounded-lg border border-c px-4 py-2 text-xs font-medium text-neutral-700 hover:bg-neutral-100 dark:text-neutral-200 dark:hover:bg-white/5"
            >
              ⬇ Unduh Laporan (format asli)
            </a>
          </>
        ) : (
          <>
            <button
              onClick={viewReport}
              disabled={busy}
              className="rounded-lg bg-[color:var(--brand)] px-4 py-2 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-50"
            >
              👁 Lihat Laporan (PDF)
            </button>
            <button
              onClick={downloadReport}
              disabled={busy}
              className="rounded-lg border border-c px-4 py-2 text-xs font-medium text-neutral-700 hover:bg-neutral-100 disabled:opacity-50 dark:text-neutral-200 dark:hover:bg-white/5"
            >
              ⬇ Unduh Laporan
            </button>
          </>
        )}
      </div>
      {hasOriginal && (
        <p className="-mt-3 text-[11px] text-neutral-400">
          Laporan mempertahankan tata letak berkas asli; temuan ditandai langsung di atas halaman
          dokumen beserta sampul ringkasan integritas.
        </p>
      )}

      {report.report_id && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg border border-c bg-neutral-50 px-3 py-2 text-[11px] text-neutral-500 dark:bg-white/5 dark:text-neutral-400">
          <span>
            🆔 ID Laporan:{" "}
            <span className="font-mono font-semibold text-neutral-700 dark:text-neutral-200">
              {report.report_id}
            </span>
          </span>
          <span>
            📚 Dibandingkan dengan{" "}
            <span className="font-semibold text-neutral-700 dark:text-neutral-200">
              {(report.corpus_size || 0).toLocaleString("id-ID")}
            </span>{" "}
            dokumen akses-terbuka
          </span>
          {report.content_sha256 && (
            <span>
              🔒 SHA-256: <span className="font-mono">{report.content_sha256.slice(0, 16)}…</span>
            </span>
          )}
          {report.generated_at && (
            <span>🕒 {new Date(report.generated_at).toLocaleString("id-ID")}</span>
          )}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-8">
        <ScoreRing
          value={shownIndex}
          label={filtersActive ? "Similarity (disesuaikan)" : "Similarity Index"}
          tone={toneForScore(shownIndex)}
        />
        <div className="min-w-0 flex-1">
          <div className="text-lg font-bold text-neutral-900 dark:text-neutral-100">
            {verdictFor(shownIndex).label}
          </div>
          <p className="mt-0.5 max-w-md text-xs text-neutral-500 dark:text-neutral-400">
            {verdictFor(shownIndex).note}
          </p>
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-neutral-500 dark:text-neutral-400">
            <span>
              {report.word_count} kata · {report.char_count} karakter
            </span>
            <span>
              {report.matched_sentences}/{report.total_sentences} kalimat cocok persis
            </span>
            {typeof report.copy_similarity === "number" && (
              <span>Salinan langsung {report.copy_similarity.toFixed(0)}%</span>
            )}
            <span>
              Risiko parafrase {report.paraphrase_similarity.toFixed(0)}% (semantik ~
              {(report.semantic_coverage_pct ?? 0).toFixed(0)}% korpus)
            </span>
          </div>
        </div>
      </div>

      {report.match_groups && report.match_groups.some((g) => g.count > 0) && (
        <div>
          <div className="mb-2 text-sm font-semibold text-neutral-800 dark:text-neutral-200">
            Kelompok Kecocokan
          </div>
          <ul className="grid gap-2 sm:grid-cols-2">
            {MATCH_GROUP_ORDER.map((key) => {
              const g = report.match_groups?.find((x) => x.type === key);
              const meta = MATCH_GROUP_META[key];
              return (
                <li key={key} className="flex items-center gap-3 rounded-lg border border-c px-3 py-2">
                  <span
                    className="mt-0.5 h-3 w-3 shrink-0 rounded-full"
                    style={{ background: meta.dot }}
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-medium text-neutral-800 dark:text-neutral-100">
                        {meta.label}
                      </span>
                      <span className="shrink-0 text-xs font-semibold text-neutral-600 dark:text-neutral-300">
                        {g?.count ?? 0} · {(g?.percent ?? 0).toFixed(1)}%
                      </span>
                    </div>
                    <p className="truncate text-[11px] text-neutral-400">{meta.desc}</p>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      <div className="rounded-lg border border-c bg-neutral-50 px-3 py-2.5 dark:bg-white/5">
        <div className="mb-1.5 text-xs font-semibold text-neutral-700 dark:text-neutral-200">
          Pengaturan Exclude (skor dihitung ulang)
        </div>
        <div className="flex flex-wrap gap-x-5 gap-y-1.5 text-xs text-neutral-600 dark:text-neutral-300">
          <label className="inline-flex cursor-pointer items-center gap-2">
            <input type="checkbox" checked={exShort} onChange={(e) => setExShort(e.target.checked)} />
            Kecualikan kecocokan pendek (&lt; {MIN_WORDS} kata)
          </label>
          <label className="inline-flex cursor-pointer items-center gap-2">
            <input type="checkbox" checked={exSmall} onChange={(e) => setExSmall(e.target.checked)} />
            Kecualikan sumber kecil (&lt; {MIN_PCT}%)
          </label>
          <label className="inline-flex cursor-pointer items-center gap-2">
            <input type="checkbox" checked={exQuotes} onChange={(e) => setExQuotes(e.target.checked)} />
            Kecualikan teks dalam kutipan
          </label>
          <label className="inline-flex cursor-pointer items-center gap-2">
            <input type="checkbox" checked={exBib} onChange={(e) => setExBib(e.target.checked)} />
            Kecualikan daftar pustaka
          </label>
        </div>
        {filtersActive && (
          <p className="mt-1.5 text-[11px] text-neutral-400">
            Skor disesuaikan dari {headlineIndex.toFixed(1)}% → {shownIndex.toFixed(1)}%
            setelah filter diterapkan.
          </p>
        )}
      </div>

      {hi.sources.length > 0 && (
        <div>
          <div className="mb-2 text-sm font-semibold text-neutral-800 dark:text-neutral-200">
            Ringkasan Kecocokan ({hi.sources.length} sumber)
          </div>
          <ul className="space-y-1.5">
            {hi.sources.map((s, i) => (
              <li key={s.key} className="flex items-center gap-2 text-xs">
                <span
                  className="flex h-5 w-5 shrink-0 items-center justify-center rounded text-[11px] font-bold text-neutral-900"
                  style={{ background: HILITE[s.color].bg, border: `1px solid ${HILITE[s.color].bd}` }}
                >
                  {i + 1}
                </span>
                <span className="font-bold text-neutral-700 dark:text-neutral-200">
                  {s.pct.toFixed(1)}%
                </span>
                <span className="min-w-0 flex-1 truncate text-neutral-500 dark:text-neutral-400">
                  {s.title || "(tanpa judul)"}
                  {s.doi ? ` · ${s.doi}` : ""}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {text && (
        <div>
          <div className="mb-2 text-sm font-semibold text-neutral-800 dark:text-neutral-200">
            Dokumen dengan Sorotan
          </div>
          <div
            className="max-h-96 overflow-auto whitespace-pre-wrap rounded-lg border border-c bg-white p-4 text-sm leading-relaxed text-neutral-800 dark:bg-neutral-900 dark:text-neutral-100"
            dangerouslySetInnerHTML={{ __html: hi.html || escHtml(text) }}
          />
          <p className="mt-1 text-[11px] text-neutral-400">
            Bagian yang disorot cocok dengan sumber bernomor pada ringkasan di atas.
            {report.document_truncated && " (Dokumen panjang — ditampilkan sebagian.)"}
          </p>
        </div>
      )}

      <div>
        <div className="mb-2 text-sm font-semibold text-neutral-800 dark:text-neutral-200">
          Sumber Teratas
        </div>
        <ul className="space-y-3">
          {report.sources.map((s) => (
            <li key={s.doc_id} className="rounded-lg border border-c p-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium text-neutral-900 dark:text-neutral-100">
                    {s.title || "(tanpa judul)"}
                  </div>
                  <div className="mt-0.5 text-xs text-neutral-400 dark:text-neutral-500">
                    {s.source}
                    {s.pub_year ? ` · ${s.pub_year}` : ""}
                    {s.doi ? (
                      <>
                        {" · "}
                        <a
                          href={`https://doi.org/${s.doi}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="underline"
                        >
                          {s.doi}
                        </a>
                      </>
                    ) : null}
                  </div>
                </div>
                <div className="shrink-0 text-right text-xs">
                  <div className={`font-bold ${toneForScore(s.similarity).split(" ")[1]}`}>
                    {s.similarity.toFixed(0)}%
                  </div>
                  <div className="text-neutral-400 dark:text-neutral-500">
                    sal {s.lexical_similarity.toFixed(0)} · sem {s.semantic_similarity.toFixed(0)}
                  </div>
                </div>
              </div>
              {s.snippet && (
                <p className="mt-2 line-clamp-3 text-xs text-neutral-500 dark:text-neutral-400">
                  {s.snippet}
                </p>
              )}
            </li>
          ))}
        </ul>
      </div>

      <div className="rounded-lg border border-c bg-neutral-50 p-3 dark:bg-white/5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="min-w-0">
            <div className="text-sm font-semibold text-neutral-800 dark:text-neutral-200">
              🌐 Cek Sumber Daring (akademik, tanpa unduh)
            </div>
            <p className="mt-0.5 text-[11px] text-neutral-500 dark:text-neutral-400">
              Memeriksa kalimat paling khas secara langsung ke OpenAlex, Crossref, arXiv, dan
              Wikipedia. Pelengkap korpus lokal — bisa memakan beberapa puluh detik.
            </p>
          </div>
          <button
            onClick={runOnline}
            disabled={onlineBusy || !text.trim()}
            className="shrink-0 rounded-lg bg-[color:var(--brand)] px-4 py-2 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-50"
          >
            {onlineBusy ? "Memeriksa…" : online ? "Periksa Ulang" : "Mulai Cek Daring"}
          </button>
        </div>

        {onlineErr && (
          <div className="mt-2 rounded-lg border border-rose-200 bg-rose-50 p-2 text-xs text-rose-700 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300">
            {onlineErr}
          </div>
        )}

        {online && (
          <div className="mt-3 space-y-3">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-neutral-600 dark:text-neutral-300">
              <span>
                Kecocokan daring:{" "}
                <b className={toneForScore(online.integrity_index).split(" ")[1]}>
                  {online.integrity_index.toFixed(1)}%
                </b>
              </span>
              <span>
                {online.matched_sentences}/{online.total_sentences} kalimat cocok
              </span>
              <span>{online.queried_sentences} kalimat diperiksa</span>
              <span>{online.candidates_checked} kandidat ditarik</span>
              {online.providers.map((p) => (
                <span key={p.name} className="rounded-full border border-c px-2 py-0.5">
                  {p.name}: {p.hits}
                </span>
              ))}
            </div>

            {online.sources.length > 0 ? (
              <ul className="space-y-1.5">
                {online.sources.map((s, i) => (
                  <li
                    key={i}
                    className="flex items-center gap-2 rounded-lg border border-c bg-white px-3 py-2 text-xs dark:bg-neutral-900"
                  >
                    <span className="shrink-0 rounded bg-[color:var(--brand-soft)] px-1.5 py-0.5 text-[10px] font-semibold text-neutral-600 dark:text-neutral-300">
                      {s.source}
                    </span>
                    <span className="min-w-0 flex-1 truncate text-neutral-700 dark:text-neutral-200">
                      {s.url ? (
                        <a
                          href={s.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="underline"
                        >
                          {s.title || s.doi || s.url}
                        </a>
                      ) : (
                        s.title || s.doi || "(tanpa judul)"
                      )}
                    </span>
                    <span className="shrink-0 font-semibold text-neutral-500 dark:text-neutral-400">
                      {s.matches} bagian
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-neutral-500 dark:text-neutral-400">
                Tidak ditemukan kecocokan daring pada sampel kalimat yang diperiksa.
              </p>
            )}

            {online.coverage_note && (
              <p className="text-[11px] text-neutral-400">{online.coverage_note}</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
