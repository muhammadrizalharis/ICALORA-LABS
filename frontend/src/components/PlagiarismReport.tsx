"use client";

import { useState } from "react";
import { downloadPdfReport } from "@/lib/download";
import { API_BASE } from "@/lib/api";
import {
  HILITE,
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
  const [busy, setBusy] = useState(false);

  const text = documentText ?? report.document_text ?? "";

  // Pengaturan Exclude dipilih SEBELUM cek & diterapkan di sisi server; laporan
  // hanya menampilkan hasil yang sudah difilter + ringkasan setelan terkunci.
  const passages: MatchedPassage[] = report.matched_passages;
  const hiOptsConst = { minWords: 0, exclude: new Set<string>() };

  function reportHtml(): string {
    return buildReportHtml({
      report,
      text,
      docTitle,
      passages,
      hiOpts: hiOptsConst,
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

  const hi = buildHighlight(text, passages, report.char_count, false, hiOptsConst);
  const shownIndex = report.integrity_index ?? report.overall_similarity;
  const ex = report.exclude_settings;
  const exLabels: string[] = [];
  if (ex?.bibliography) exLabels.push("Tanpa daftar pustaka");
  if (ex?.quotes) exLabels.push("Tanpa kutipan");
  if (ex && ex.min_source_percent > 0)
    exLabels.push(`Kecualikan sumber < ${ex.min_source_percent}%`);

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
          dokumen beserta sampul ringkasan kemiripan.
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
            📚 Dibandingkan dengan korpus akses-terbuka
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
          label="Similarity Index"
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
        <div className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-neutral-700 dark:text-neutral-200">
          <span>🔒</span> Pengaturan Exclude (dikunci saat pemeriksaan)
        </div>
        {exLabels.length > 0 ? (
          <div className="flex flex-wrap gap-1.5">
            {exLabels.map((l) => (
              <span
                key={l}
                className="rounded-full border border-c bg-white px-2.5 py-1 text-[11px] font-medium text-neutral-600 dark:bg-white/10 dark:text-neutral-300"
              >
                {l}
              </span>
            ))}
          </div>
        ) : (
          <p className="text-[11px] text-neutral-400">
            Tidak ada pengecualian — seluruh kecocokan dihitung.
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
          {report.sources.map((s, i) => (
            <li key={s.doc_id ?? `online-${i}`} className="rounded-lg border border-c p-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium text-neutral-900 dark:text-neutral-100">
                    {s.online && (
                      <span className="mr-1 rounded bg-sky-500 px-1 py-0.5 align-middle text-[10px] font-semibold text-white">
                        DARING
                      </span>
                    )}
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
                    {s.similarity.toFixed(1)}%
                  </div>
                  <div className="text-[10px] text-neutral-400 dark:text-neutral-500">
                    kecocokan
                  </div>
                  <div className="mt-0.5 text-neutral-400 dark:text-neutral-500">
                    {s.source_containment && s.source_containment >= 40
                      ? `abstrak ${s.source_containment.toFixed(0)}% termuat`
                      : `topik ${s.semantic_similarity.toFixed(0)}%`}
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
    </div>
  );
}
