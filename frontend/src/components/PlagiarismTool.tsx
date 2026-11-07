"use client";

import { useState } from "react";
import { apiPost } from "@/lib/api";
import { downloadPdfReport } from "@/lib/download";
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
  report_id?: string;
  content_sha256?: string;
  corpus_size?: number;
  generated_at?: string;
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

const HILITE = [
  { bg: "#fde68a", bd: "#d97706" },
  { bg: "#bfdbfe", bd: "#2563eb" },
  { bg: "#bbf7d0", bd: "#16a34a" },
  { bg: "#fbcfe8", bd: "#db2777" },
  { bg: "#ddd6fe", bd: "#7c3aed" },
  { bg: "#fed7aa", bd: "#ea580c" },
  { bg: "#a5f3fc", bd: "#0891b2" },
  { bg: "#e9d5ff", bd: "#9333ea" },
];

function escHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

interface SrcAgg {
  key: string;
  title: string | null;
  doi: string | null;
  color: number;
  chars: number;
  count: number;
  pct: number;
  num: number;
}

function passageKey(p: MatchedPassage): string {
  return p.source_title || (p.doc_id != null ? `doc-${p.doc_id}` : "src");
}

/** Bangun HTML dokumen dengan sorotan warna + badge nomor per sumber. */
function buildHighlight(
  original: string,
  passages: MatchedPassage[],
  charCount: number,
  linked = false,
): { html: string; sources: SrcAgg[] } {
  const map = new Map<string, SrcAgg>();
  const order: string[] = [];
  for (const p of passages) {
    const key = passageKey(p);
    if (!map.has(key)) {
      map.set(key, {
        key,
        title: p.source_title,
        doi: p.source_doi,
        color: order.length % HILITE.length,
        chars: 0,
        count: 0,
        pct: 0,
        num: 0,
      });
      order.push(key);
    }
  }

  const lower = original.toLowerCase();
  const ranges: { start: number; end: number; key: string }[] = [];
  for (const p of passages) {
    const needle = p.sentence.trim().toLowerCase();
    if (needle.length < 10) continue;
    let idx = lower.indexOf(needle);
    let len = needle.length;
    if (idx < 0) {
      const frag = needle.slice(0, 80);
      idx = lower.indexOf(frag);
      len = frag.length;
      if (idx < 0) continue;
    }
    ranges.push({ start: idx, end: idx + len, key: passageKey(p) });
  }

  ranges.sort((a, b) => a.start - b.start);
  const merged: { start: number; end: number; key: string }[] = [];
  let lastEnd = -1;
  for (const r of ranges) {
    if (r.start >= lastEnd) {
      merged.push(r);
      lastEnd = r.end;
    }
  }

  for (const r of merged) {
    const agg = map.get(r.key)!;
    agg.chars += r.end - r.start;
    agg.count += 1;
  }

  const sources = order
    .map((k) => {
      const a = map.get(k)!;
      a.pct = Math.round((a.chars / Math.max(charCount, 1)) * 1000) / 10;
      return a;
    })
    .filter((a) => a.count > 0)
    .sort((a, b) => b.pct - a.pct);
  sources.forEach((a, i) => {
    a.num = i + 1;
  });

  let html = "";
  let pos = 0;
  for (const r of merged) {
    if (r.start > pos) html += escHtml(original.slice(pos, r.start));
    const agg = map.get(r.key)!;
    const c = HILITE[agg.color];
    const badge = linked
      ? `<a class="hlnum" href="#src-${agg.num}" style="background:${c.bd};">${agg.num}</a>`
      : `<span class="hlnum" style="background:${c.bd};">${agg.num}</span>`;
    html += `<span class="hl" style="background:${c.bg};border-bottom:2px solid ${c.bd};">${badge}${escHtml(
      original.slice(r.start, r.end),
    )}</span>`;
    pos = r.end;
  }
  if (pos < original.length) html += escHtml(original.slice(pos));

  return { html, sources };
}

function verdictFor(v: number): { label: string; note: string } {
  if (v >= 40)
    return {
      label: "Kemiripan tinggi",
      note: "Indeks kemiripan tinggi — banyak bagian cocok dengan sumber. Perlu ditinjau serius dan diparafrase/disitasi.",
    };
  if (v >= 15)
    return {
      label: "Kemiripan sedang",
      note: "Terdapat kemiripan pada beberapa bagian — tinjau teks yang disorot dan pastikan sudah disitasi dengan benar.",
    };
  return {
    label: "Kemiripan rendah",
    note: "Indeks kemiripan rendah — dokumen relatif orisinal terhadap korpus yang dibandingkan.",
  };
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
      const res = await apiPost<Report>("/tools/plagiarism", { text, top_k: 30 });
      setReport(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Terjadi kesalahan");
    } finally {
      setLoading(false);
    }
  }

  function downloadReport() {
    if (!report) return;
    const now = new Date().toLocaleString("id-ID");
    const idx = report.overall_similarity;
    const v = verdictFor(idx);
    const { html: hiText, sources: hiSources } = buildHighlight(
      text,
      report.matched_passages,
      report.char_count,
      true,
    );

    const overview = hiSources
      .map((s, i) => {
        const c = HILITE[s.color];
        return `<tr id="src-${i + 1}">
  <td class="num"><span class="swatch" style="background:${c.bd};">${i + 1}</span></td>
  <td class="pct">${s.pct.toFixed(1)}%</td>
  <td>${escHtml(s.title || "(tanpa judul)")}${
    s.doi ? `<div class="src">${escHtml(s.doi)}</div>` : ""
  }<div class="src">${s.count} bagian cocok</div></td>
</tr>`;
      })
      .join("");

    const sources = report.sources
      .map(
        (s) => `<tr><td class="pct">${s.similarity.toFixed(0)}%</td><td>${escHtml(
          s.title || "(tanpa judul)",
        )}<div class="src">${escHtml(s.source)}${s.pub_year ? ` · ${s.pub_year}` : ""}${
          s.doi ? ` · ${escHtml(s.doi)}` : ""
        } · salinan ${s.lexical_similarity.toFixed(0)}% · semantik ${s.semantic_similarity.toFixed(
          0,
        )}%</div></td></tr>`,
      )
      .join("");

    const ringCls = ringClass(idx);
    const html = `<!doctype html><html lang="id"><head><meta charset="utf-8">
<title>Laporan Kemiripan — ICALORA-LABS</title>
<style>
  body{font-family:system-ui,Segoe UI,Roboto,sans-serif;color:#1a202c;max-width:820px;margin:28px auto;padding:0 28px;font-size:13px;line-height:1.5;}
  .head{display:flex;justify-content:space-between;align-items:flex-start;border-bottom:2px solid #0e1726;padding-bottom:12px;}
  h1{font-size:19px;margin:0;} .brand{font-size:11px;color:#64748b;margin-top:2px;}
  .sid{font-size:11px;color:#94a3b8;text-align:right;}
  .hero{display:flex;gap:22px;align-items:center;margin:22px 0 10px;}
  .ring{border:7px solid;border-radius:50%;width:112px;height:112px;display:flex;flex-direction:column;align-items:center;justify-content:center;flex:none;}
  .ring .big{font-size:30px;font-weight:800;line-height:1;} .ring .cap{font-size:9px;letter-spacing:.5px;margin-top:3px;}
  .ring.c-red{border-color:#f87171;color:#dc2626;} .ring.c-amber{border-color:#fbbf24;color:#d97706;} .ring.c-green{border-color:#34d399;color:#059669;}
  .verdict{font-size:17px;font-weight:700;} .vnote{color:#475569;font-size:12px;margin-top:4px;max-width:520px;}
  .metrics{display:flex;gap:18px;flex-wrap:wrap;margin:8px 0 4px;font-size:12px;color:#334155;}
  .metrics b{color:#0e1726;}
  h2{font-size:13px;text-transform:uppercase;letter-spacing:.6px;color:#0e1726;border-bottom:1px solid #e2e8f0;padding-bottom:6px;margin-top:26px;}
  table{width:100%;border-collapse:collapse;font-size:12px;} td{padding:7px 8px;border-bottom:1px solid #eef2f7;vertical-align:top;}
  td.pct{width:52px;font-weight:700;text-align:center;color:#0e1726;} td.num{width:30px;}
  .swatch{display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;border-radius:50%;font-size:11px;font-weight:700;color:#fff;}
  .src{color:#94a3b8;font-size:11px;margin-top:2px;}
  .doc{border:1px solid #e2e8f0;border-radius:8px;padding:14px 16px 14px 30px;font-size:12.5px;line-height:1.9;white-space:pre-wrap;word-wrap:break-word;background:#fff;}
  .hl{border-radius:2px;padding:0 1px;}
  .hlnum{display:inline-block;min-width:14px;height:14px;line-height:14px;padding:0 3px;margin:0 3px 0 -18px;border-radius:7px;color:#fff;font-size:9px;font-weight:700;text-align:center;vertical-align:middle;text-decoration:none;}
  a.hlnum{text-decoration:none;}
  .legend{font-size:11px;color:#64748b;margin:8px 0 0;}
  footer{margin-top:34px;color:#94a3b8;font-size:11px;text-align:center;border-top:1px solid #e2e8f0;padding-top:12px;}
  @media print{body{margin:0;}}
</style></head><body>
<div class="head">
  <div><h1>Laporan Indeks Kemiripan</h1><div class="brand">ICALORA-LABS · MRH INNOVEX — Deteksi plagiarisme yang sah & terpercaya (self-hosted)</div></div>
  <div class="sid">ID Laporan: <b>${escHtml(report.report_id || "-")}</b><br>Dibuat ${escHtml(
    report.generated_at ? new Date(report.generated_at).toLocaleString("id-ID") : now,
  )}<br>Dibandingkan dengan <b>${(report.corpus_size || 0).toLocaleString(
    "id-ID",
  )}</b> dokumen akses-terbuka (CC0/CC-BY)</div>
</div>
<div class="hero">
  <div class="ring ${ringCls}"><span class="big">${idx.toFixed(0)}%</span><span class="cap">SIMILARITY</span></div>
  <div><div class="verdict">${v.label}</div><div class="vnote">${v.note}</div></div>
</div>
<div class="metrics">
  <div><b>${report.word_count}</b> kata</div>
  <div><b>${report.char_count}</b> karakter</div>
  <div><b>${report.matched_sentences}/${report.total_sentences}</b> kalimat cocok persis</div>
  <div><b>${report.paraphrase_similarity.toFixed(0)}%</b> risiko parafrase (semantik)</div>
  <div><b>${(report.corpus_size || 0).toLocaleString("id-ID")}</b> dokumen dibandingkan · <b>${report.sources.length}</b> sumber teratas</div>
</div>
${
  overview
    ? `<h2>Ringkasan Kecocokan (Match Overview)</h2><table>${overview}</table>`
    : `<p class="legend">Tidak ada kalimat yang cocok persis dengan sumber.</p>`
}
<h2>Dokumen dengan Sorotan</h2>
<div class="doc">${hiText || escHtml(text)}</div>
<p class="legend">Setiap teks tersorot diberi <b>penanda nomor bulat</b> sesuai sumbernya pada Ringkasan Kecocokan di atas. Klik penanda untuk melompat ke sumber terkait.</p>
<h2>Sumber Teratas</h2><table>${sources}</table>
<footer>Dibandingkan dengan <b>${(report.corpus_size || 0).toLocaleString(
      "id-ID",
    )}</b> dokumen korpus akses-terbuka ICALORA-LABS. ID Laporan <b>${escHtml(
      report.report_id || "-",
    )}</b> · Hash integritas SHA-256: ${escHtml(
      (report.content_sha256 || "").slice(0, 32),
    )}…<br>Laporan ini bersifat indikatif untuk tinjauan akademik, bukan vonis plagiarisme final. ID &amp; hash bersifat reproducible: teks yang sama menghasilkan ID yang sama sehingga laporan dapat diverifikasi.</footer>
</body></html>`;
    downloadPdfReport(`laporan-kemiripan-${Date.now()}.pdf`, html);
  }

  const hi = report ? buildHighlight(text, report.matched_passages, report.char_count) : null;

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
          {report.report_id && (
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg border border-c bg-neutral-50 px-3 py-2 text-[11px] text-neutral-500 dark:bg-white/5 dark:text-neutral-400">
              <span>🆔 ID Laporan: <span className="font-mono font-semibold text-neutral-700 dark:text-neutral-200">{report.report_id}</span></span>
              <span>📚 Dibandingkan dengan <span className="font-semibold text-neutral-700 dark:text-neutral-200">{(report.corpus_size || 0).toLocaleString("id-ID")}</span> dokumen akses-terbuka</span>
              {report.content_sha256 && (
                <span>🔒 SHA-256: <span className="font-mono">{report.content_sha256.slice(0, 16)}…</span></span>
              )}
              {report.generated_at && (
                <span>🕒 {new Date(report.generated_at).toLocaleString("id-ID")}</span>
              )}
            </div>
          )}
          <div className="flex flex-wrap items-center gap-8">
            <ScoreRing
              value={report.overall_similarity}
              label="Similarity Index"
              tone={toneForScore(report.overall_similarity)}
            />
            <div className="min-w-0 flex-1">
              <div className="text-lg font-bold text-neutral-900 dark:text-neutral-100">
                {verdictFor(report.overall_similarity).label}
              </div>
              <p className="mt-0.5 max-w-md text-xs text-neutral-500 dark:text-neutral-400">
                {verdictFor(report.overall_similarity).note}
              </p>
              <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-neutral-500 dark:text-neutral-400">
                <span>{report.word_count} kata · {report.char_count} karakter</span>
                <span>{report.matched_sentences}/{report.total_sentences} kalimat cocok persis</span>
                <span>Risiko parafrase {report.paraphrase_similarity.toFixed(0)}%</span>
                <span>{(report.corpus_size || 0).toLocaleString("id-ID")} dokumen dibandingkan · {report.sources.length} sumber teratas</span>
              </div>
              <button
                onClick={downloadReport}
                className="mt-2 rounded-lg border border-c px-3 py-1.5 text-xs font-medium text-neutral-700 hover:bg-neutral-100 dark:text-neutral-200 dark:hover:bg-white/5"
              >
                ⬇ Unduh Laporan (PDF)
              </button>
            </div>
          </div>

          {hi && hi.sources.length > 0 && (
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

          {hi && (
            <div>
              <div className="mb-2 text-sm font-semibold text-neutral-800 dark:text-neutral-200">
                Dokumen dengan Sorotan
              </div>
              <div
                className="max-h-80 overflow-auto whitespace-pre-wrap rounded-lg border border-c bg-white p-4 text-sm leading-relaxed text-neutral-800 dark:bg-neutral-900 dark:text-neutral-100"
                dangerouslySetInnerHTML={{ __html: hi.html || escHtml(text) }}
              />
              <p className="mt-1 text-[11px] text-neutral-400">
                Bagian yang disorot cocok dengan sumber bernomor pada ringkasan di atas.
              </p>
            </div>
          )}

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
