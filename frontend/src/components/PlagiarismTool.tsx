"use client";

import { useState } from "react";
import { apiPost } from "@/lib/api";
import TextInput from "@/components/TextInput";

interface Source {
  doc_id: number;
  source: string;
  external_id: string;
  doi: string | null;
  title: string | null;
  pub_year: number | null;
  semantic_similarity: number;
  lexical_similarity: number;
  similarity: number;
  snippet: string;
}

interface MatchedPassage {
  sentence: string;
  match_ratio: number;
  source_title: string | null;
  source_doi: string | null;
  doc_id: number | null;
}

interface Report {
  overall_similarity: number;
  document_lexical_similarity: number;
  paraphrase_similarity: number;
  similarity_index: number;
  matched_sentences: number;
  total_sentences: number;
  matched_passages: MatchedPassage[];
  word_count: number;
  char_count: number;
  sources: Source[];
}

function ScoreRing({ value, label, tone }: { value: number; label: string; tone: string }) {
  return (
    <div className="flex flex-col items-center">
      <div
        className={`flex h-24 w-24 items-center justify-center rounded-full border-4 text-2xl font-bold ${tone}`}
      >
        {value.toFixed(0)}%
      </div>
      <div className="mt-2 text-center text-xs font-medium text-neutral-500 dark:text-neutral-400">{label}</div>
    </div>
  );
}

function toneForScore(v: number): string {
  if (v >= 40) return "border-red-400 text-red-600";
  if (v >= 15) return "border-amber-400 text-amber-600";
  return "border-emerald-400 text-emerald-600";
}

function ringClass(v: number): string {
  if (v >= 40) return "c-red";
  if (v >= 15) return "c-amber";
  return "c-green";
}

export default function PlagiarismTool() {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<Report | null>(null);

  async function run() {
    setLoading(true);
    setError(null);
    setReport(null);
    try {
      const res = await apiPost<Report>("/tools/plagiarism", { text, top_k: 10 });
      setReport(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Terjadi kesalahan");
    } finally {
      setLoading(false);
    }
  }

  function downloadReport() {
    if (!report) return;
    const esc = (s: string) =>
      s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    const now = new Date().toLocaleString("id-ID");
    const passages = report.matched_passages
      .map(
        (p) => `<tr><td class="r">${p.match_ratio.toFixed(0)}%</td><td>&ldquo;${esc(
          p.sentence,
        )}&rdquo;${
          p.source_title ? `<div class="src">↳ ${esc(p.source_title)}${p.source_doi ? ` · ${esc(p.source_doi)}` : ""}</div>` : ""
        }</td></tr>`,
      )
      .join("");
    const sources = report.sources
      .map(
        (s) => `<tr><td class="r">${s.similarity.toFixed(0)}%</td><td>${esc(
          s.title || "(tanpa judul)",
        )}<div class="src">${esc(s.source)}${s.pub_year ? ` · ${s.pub_year}` : ""}${
          s.doi ? ` · ${esc(s.doi)}` : ""
        }</div></td></tr>`,
      )
      .join("");
    const html = `<!doctype html><html lang="id"><head><meta charset="utf-8">
<title>Laporan Kemiripan — ICALORA-LABS</title>
<style>
  body{font-family:system-ui,Segoe UI,Roboto,sans-serif;color:#1a202c;max-width:820px;margin:32px auto;padding:0 24px;}
  h1{font-size:20px;margin:0;} .sub{color:#64748b;font-size:12px;margin-bottom:24px;}
  .scores{display:flex;gap:24px;margin:16px 0 28px;}
  .ring{border:4px solid;border-radius:50%;width:92px;height:92px;display:flex;align-items:center;justify-content:center;font-size:22px;font-weight:700;}
  .ring.c-red{border-color:#f87171;color:#dc2626;} .ring.c-amber{border-color:#fbbf24;color:#d97706;} .ring.c-green{border-color:#34d399;color:#059669;}
  .lbl{font-size:11px;color:#64748b;text-align:center;margin-top:6px;max-width:100px;}
  h2{font-size:14px;border-bottom:1px solid #e2e8f0;padding-bottom:6px;margin-top:28px;}
  table{width:100%;border-collapse:collapse;font-size:12px;} td{padding:8px;border-bottom:1px solid #eef2f7;vertical-align:top;}
  td.r{width:52px;font-weight:700;text-align:center;} .src{color:#94a3b8;font-size:11px;margin-top:3px;}
  .meta{font-size:12px;color:#64748b;} footer{margin-top:40px;color:#94a3b8;font-size:11px;text-align:center;}
  @media print{body{margin:0;}}
</style></head><body>
<h1>Laporan Indeks Kemiripan</h1>
<div class="sub">ICALORA-LABS · MRH INNOVEX — dibuat ${esc(now)}</div>
<div class="scores">
  <div><div class="ring ${ringClass(report.overall_similarity)}">${report.overall_similarity.toFixed(0)}%</div><div class="lbl">Indeks Kemiripan (salinan)</div></div>
  <div><div class="ring ${ringClass(report.paraphrase_similarity)}">${report.paraphrase_similarity.toFixed(0)}%</div><div class="lbl">Risiko Parafrase (semantik)</div></div>
</div>
<div class="meta">${report.word_count} kata · ${report.char_count} karakter · ${report.matched_sentences}/${report.total_sentences} kalimat cocok persis · ${report.sources.length} sumber dibandingkan.</div>
${passages ? `<h2>Kalimat Terdeteksi Menyalin</h2><table>${passages}</table>` : ""}
<h2>Sumber Teratas</h2><table>${sources}</table>
<footer>Dibandingkan dengan korpus akses-terbuka ICALORA-LABS. Laporan ini bersifat indikatif untuk tinjauan akademik.</footer>
</body></html>`;
    const blob = new Blob([html], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `laporan-kemiripan-${Date.now()}.html`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-5">
      <TextInput
        value={text}
        onChange={setText}
        placeholder="Tempel teks/abstrak yang ingin diperiksa keasliannya…"
        rows={10}
      />
      <div className="flex items-center gap-3">
        <button
          onClick={run}
          disabled={loading || text.trim().length === 0}
          className="rounded-lg bg-neutral-900 px-5 py-2 text-sm font-medium text-white disabled:opacity-40 dark:bg-neutral-100 dark:text-neutral-900"
        >
          {loading ? "Memeriksa…" : "Periksa Kemiripan"}
        </button>
        <span className="text-xs text-neutral-400 dark:text-neutral-500">
          Dibandingkan dengan korpus akses-terbuka ICALORA-LABS.
        </span>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
          {error}
        </div>
      )}

      {report && (
        <div className="space-y-5 rounded-xl border border-c p-5">
          <div className="flex flex-wrap items-center gap-8">
            <ScoreRing
              value={report.overall_similarity}
              label="Indeks Kemiripan (salinan)"
              tone={toneForScore(report.overall_similarity)}
            />
            <ScoreRing
              value={report.paraphrase_similarity}
              label="Risiko Parafrase (semantik)"
              tone={toneForScore(report.paraphrase_similarity)}
            />
            <div className="text-sm text-neutral-500 dark:text-neutral-400">
              <div>{report.word_count} kata · {report.char_count} karakter</div>
              <div>{report.sources.length} sumber teratas ditemukan</div>
              <div>
                {report.matched_sentences}/{report.total_sentences} kalimat cocok persis
              </div>
              <button
                onClick={downloadReport}
                className="mt-2 rounded-lg border border-c px-3 py-1.5 text-xs font-medium text-neutral-700 hover:bg-neutral-100 dark:text-neutral-200 dark:hover:bg-white/5"
              >
                ⬇ Unduh Laporan
              </button>
            </div>
          </div>

          {report.matched_passages.length > 0 && (
            <div>
              <div className="mb-2 text-sm font-semibold text-neutral-800 dark:text-neutral-200">
                Kalimat Terdeteksi Menyalin ({report.matched_passages.length})
              </div>
              <ul className="space-y-2">
                {report.matched_passages.map((p, i) => (
                  <li
                    key={i}
                    className="rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-900/50 dark:bg-amber-950/30"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <p className="text-xs text-neutral-700 dark:text-neutral-200">
                        &ldquo;{p.sentence}&rdquo;
                      </p>
                      <span className="shrink-0 text-xs font-bold text-amber-600 dark:text-amber-400">
                        {p.match_ratio.toFixed(0)}%
                      </span>
                    </div>
                    {p.source_title && (
                      <div className="mt-1 text-[11px] text-neutral-400">
                        ↳ {p.source_title}
                        {p.source_doi && (
                          <>
                            {" · "}
                            <a
                              href={`https://doi.org/${p.source_doi}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="underline"
                            >
                              {p.source_doi}
                            </a>
                          </>
                        )}
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div>
            <div className="mb-2 text-sm font-semibold text-neutral-800 dark:text-neutral-200">Sumber Teratas</div>
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
                    <p className="mt-2 line-clamp-3 text-xs text-neutral-500 dark:text-neutral-400">{s.snippet}</p>
                  )}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
