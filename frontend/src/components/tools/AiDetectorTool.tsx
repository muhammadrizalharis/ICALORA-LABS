"use client";

import { useState } from "react";
import { apiPost } from "@/lib/api";
import { downloadPdfReport } from "@/lib/download";
import TextInput from "@/components/TextInput";

interface Signals {
  burstiness: number;
  type_token_ratio: number;
  avg_sentence_length: number;
  bigram_repetition: number;
  cliche_density: number;
  personal_ratio: number;
  sentence_count: number;
  word_count: number;
  stat_score: number;
}
interface DetectResult {
  ai_probability: number | null;
  verdict: string;
  stat_probability?: number;
  llm_probability?: number | null;
  signals: Signals;
  flagged_sentences: string[];
  note: string;
}

function probColor(p: number): string {
  if (p >= 70) return "#ef4444";
  if (p >= 45) return "#eab308";
  return "#22c55e";
}

function escHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// Sorot kalimat yang ditandai AI secara inline di dalam dokumen asli (gaya laporan akademik).
function buildAiHighlight(text: string, flagged: string[]): string {
  const low = text.toLowerCase();
  const ranges: { start: number; end: number }[] = [];
  for (const f of flagged) {
    const needle = f.trim().toLowerCase();
    if (!needle) continue;
    let idx = low.indexOf(needle);
    let len = needle.length;
    if (idx < 0) {
      const short = needle.slice(0, 60);
      idx = low.indexOf(short);
      len = short.length;
      if (idx < 0) continue;
    }
    ranges.push({ start: idx, end: idx + len });
  }
  ranges.sort((a, b) => a.start - b.start);
  const merged: { start: number; end: number }[] = [];
  for (const r of ranges) {
    const last = merged[merged.length - 1];
    if (last && r.start < last.end) last.end = Math.max(last.end, r.end);
    else merged.push({ ...r });
  }
  let out = "";
  let cur = 0;
  for (const r of merged) {
    out += escHtml(text.slice(cur, r.start));
    out += `<span class="hl" style="background:#fde68a;border-bottom:2px solid #f59e0b;border-radius:2px;padding:0 1px;">${escHtml(
      text.slice(r.start, r.end),
    )}</span>`;
    cur = r.end;
  }
  out += escHtml(text.slice(cur));
  return out;
}

export default function AiDetectorTool() {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [res, setRes] = useState<DetectResult | null>(null);

  async function run() {
    if (!text.trim()) return;
    setLoading(true);
    setError(null);
    setRes(null);
    try {
      setRes(await apiPost<DetectResult>("/tools/ai-detect", { text }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Terjadi kesalahan.");
    } finally {
      setLoading(false);
    }
  }

  const p = res?.ai_probability ?? null;

  function ringClass(v: number): string {
    if (v >= 70) return "c-red";
    if (v >= 45) return "c-amber";
    return "c-green";
  }

  function downloadReport() {
    if (!res) return;
    const esc = escHtml;
    const now = new Date().toLocaleString("id-ID");
    const prob = res.ai_probability ?? 0;
    const flagged = (res.flagged_sentences ?? [])
      .map((s) => `<li>&ldquo;${esc(s)}&rdquo;</li>`)
      .join("");
    const hiDoc = buildAiHighlight(text, res.flagged_sentences ?? []);
    const sg = res.signals;
    const rows = [
      ["Burstiness (variasi panjang kalimat)", sg.burstiness],
      ["Keragaman kata (type–token ratio)", sg.type_token_ratio],
      ["Panjang kalimat rata-rata", sg.avg_sentence_length],
      ["Pengulangan bigram", sg.bigram_repetition],
      ["Kepadatan klise AI", sg.cliche_density],
      ["Nada personal", sg.personal_ratio],
      ["Jumlah kalimat", sg.sentence_count],
      ["Jumlah kata", sg.word_count],
    ]
      .map(([l, v]) => `<tr><td>${esc(String(l))}</td><td class="r">${v}</td></tr>`)
      .join("");
    const html = `<!doctype html><html lang="id"><head><meta charset="utf-8">
<title>Laporan Deteksi AI — ICALORA-LABS</title>
<style>
  body{font-family:system-ui,Segoe UI,Roboto,sans-serif;color:#1a202c;max-width:820px;margin:32px auto;padding:0 24px;}
  h1{font-size:20px;margin:0;} .sub{color:#64748b;font-size:12px;margin-bottom:24px;}
  .scores{display:flex;gap:24px;margin:16px 0 28px;align-items:center;}
  .ring{border:4px solid;border-radius:50%;width:92px;height:92px;display:flex;align-items:center;justify-content:center;font-size:22px;font-weight:700;}
  .ring.c-red{border-color:#f87171;color:#dc2626;} .ring.c-amber{border-color:#fbbf24;color:#d97706;} .ring.c-green{border-color:#34d399;color:#059669;}
  .verdict{font-size:16px;font-weight:600;text-transform:capitalize;} .vsub{font-size:12px;color:#64748b;}
  h2{font-size:14px;border-bottom:1px solid #e2e8f0;padding-bottom:6px;margin-top:28px;}
  table{width:100%;border-collapse:collapse;font-size:12px;} td{padding:8px;border-bottom:1px solid #eef2f7;vertical-align:top;}
  td.r{width:80px;font-weight:700;text-align:right;}
  ul{font-size:12px;padding-left:18px;} li{margin:6px 0;}
  .doc{border:1px solid #e2e8f0;border-radius:8px;padding:14px 16px;font-size:12.5px;line-height:1.75;white-space:pre-wrap;word-wrap:break-word;background:#fff;}
  .doc .hl{background:#fde68a;border-bottom:2px solid #f59e0b;border-radius:2px;padding:0 1px;}
  .legend{font-size:11px;color:#64748b;margin:8px 0 0;}
  footer{margin-top:40px;color:#94a3b8;font-size:11px;text-align:center;}
  @media print{body{margin:0;}}
</style></head><body>
<h1>Laporan Deteksi Tulisan AI</h1>
<div class="sub">ICALORA-LABS · MRH INNOVEX — dibuat ${esc(now)}</div>
<div class="scores">
  <div class="ring ${ringClass(prob)}">${prob.toFixed(0)}%</div>
  <div><div class="verdict">${esc(res.verdict)}</div><div class="vsub">kemungkinan ditulis AI${
      typeof res.stat_probability === "number"
        ? ` · statistik ${res.stat_probability}%`
        : ""
    }${typeof res.llm_probability === "number" ? ` · LLM ${res.llm_probability}%` : ""}</div></div>
</div>
${flagged ? `<h2>Kalimat yang Ditandai Mirip AI</h2><ul>${flagged}</ul>` : ""}
<h2>Dokumen dengan Sorotan</h2>
<div class="doc">${hiDoc || esc(text)}</div>
<p class="legend">Bagian yang disorot kuning adalah kalimat yang terindikasi berpola khas tulisan AI.</p>
<h2>Sinyal Analisis</h2><table>${rows}</table>
<footer>${esc(res.note)}</footer>
</body></html>`;
    downloadPdfReport(`laporan-deteksi-ai-${Date.now()}.pdf`, html);
  }

  return (
    <div className="space-y-4">
      <TextInput value={text} onChange={setText} rows={8} placeholder="Tempel teks untuk dideteksi kemungkinan ditulis AI…" />
      <button
        onClick={run}
        disabled={loading || !text.trim()}
        className="rounded-lg bg-[color:var(--brand)] px-5 py-2 text-sm font-medium text-white disabled:opacity-40"
      >
        {loading ? "Menganalisis…" : "Deteksi AI"}
      </button>
      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300">
          {error}
        </div>
      )}
      {res && (
        <div className="space-y-4">
          <div className="flex items-center gap-5 rounded-xl border border-c surface-2 p-5">
            {p !== null ? (
              <div
                className="flex h-24 w-24 items-center justify-center rounded-full text-2xl font-bold text-white"
                style={{ background: probColor(p) }}
              >
                {p}%
              </div>
            ) : (
              <div className="flex h-24 w-24 items-center justify-center rounded-full bg-neutral-300 text-sm text-white dark:bg-neutral-700">
                N/A
              </div>
            )}
            <div>
              <div className="text-lg font-semibold capitalize">{res.verdict}</div>
              <p className="text-xs text-neutral-500 dark:text-neutral-400">kemungkinan ditulis AI</p>
              {typeof res.stat_probability === "number" && (
                <p className="mt-1 text-xs text-neutral-400">
                  Statistik: {res.stat_probability}%
                  {typeof res.llm_probability === "number" && ` · LLM: ${res.llm_probability}%`}
                </p>
              )}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              ["Burstiness", res.signals.burstiness],
              ["Keragaman kata", res.signals.type_token_ratio],
              ["Panjang kalimat", res.signals.avg_sentence_length],
              ["Pengulangan bigram", res.signals.bigram_repetition],
              ["Kepadatan klise", res.signals.cliche_density],
              ["Nada personal", res.signals.personal_ratio],
              ["Jumlah kalimat", res.signals.sentence_count],
              ["Jumlah kata", res.signals.word_count],
            ].map(([l, v]) => (
              <div key={l as string} className="rounded-xl border border-c surface-2 p-4">
                <div className="text-lg font-semibold">{v}</div>
                <div className="text-xs text-neutral-500 dark:text-neutral-400">{l}</div>
              </div>
            ))}
          </div>
          {res.flagged_sentences?.length > 0 && (
            <div className="rounded-xl border border-c surface-2 p-5">
              <div className="mb-3 text-sm font-semibold">
                Kalimat yang ditandai mirip AI ({res.flagged_sentences.length})
              </div>
              <ul className="space-y-2">
                {res.flagged_sentences.map((s, i) => (
                  <li
                    key={i}
                    className="rounded-lg border-l-4 border-rose-400 bg-rose-50 p-3 text-sm text-neutral-700 dark:bg-rose-950/40 dark:text-neutral-200"
                  >
                    {s}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {res.flagged_sentences?.length > 0 && (
            <div className="rounded-xl border border-c surface-2 p-5">
              <div className="mb-3 text-sm font-semibold">Dokumen dengan sorotan</div>
              <div
                className="ai-doc whitespace-pre-wrap break-words text-sm leading-7 text-neutral-700 dark:text-neutral-200"
                dangerouslySetInnerHTML={{
                  __html: buildAiHighlight(text, res.flagged_sentences),
                }}
              />
              <p className="mt-3 text-xs text-neutral-500 dark:text-neutral-400">
                Bagian yang disorot adalah kalimat yang terindikasi berpola khas tulisan AI.
              </p>
            </div>
          )}
          <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-300">
            ⚠️ {res.note}
          </p>
          <button
            onClick={downloadReport}
            className="rounded-lg border border-c surface-2 px-4 py-2 text-sm font-medium hover:bg-black/5 dark:hover:bg-white/5"
          >
            ⬇ Unduh laporan (PDF)
          </button>
        </div>
      )}
    </div>
  );
}
