"use client";

import { useState } from "react";
import { apiPost } from "@/lib/api";
import TextInput from "@/components/TextInput";

interface Criterion {
  name: string;
  score: number;
  feedback: string;
}
interface GradeResult {
  overall_score: number | null;
  grade: string | null;
  criteria: Criterion[];
  summary: string;
  suggestions: string[];
}

function scoreColor(s: number): string {
  if (s >= 80) return "#22c55e";
  if (s >= 60) return "#eab308";
  return "#ef4444";
}

export default function GraderTool() {
  const [text, setText] = useState("");
  const [rubric, setRubric] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [res, setRes] = useState<GradeResult | null>(null);

  async function run() {
    if (!text.trim()) return;
    setLoading(true);
    setError(null);
    setRes(null);
    try {
      const d = await apiPost<GradeResult>("/tools/grade", {
        text,
        rubric: rubric.trim() || null,
      });
      setRes(d);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Terjadi kesalahan.");
    } finally {
      setLoading(false);
    }
  }

  function downloadReport() {
    if (!res) return;
    const esc = (s: string) =>
      s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    const now = new Date().toLocaleString("id-ID");
    const ringClass = (v: number) => (v >= 80 ? "c-green" : v >= 60 ? "c-amber" : "c-red");
    const criteria = res.criteria
      .map(
        (c) =>
          `<tr><td class="r">${c.score}</td><td><b>${esc(c.name)}</b><div class="src">${esc(
            c.feedback,
          )}</div></td></tr>`,
      )
      .join("");
    const suggestions = res.suggestions.map((s) => `<li>${esc(s)}</li>`).join("");
    const html = `<!doctype html><html lang="id"><head><meta charset="utf-8">
<title>Laporan Penilaian Esai — ICALORA-LABS</title>
<style>
  body{font-family:system-ui,Segoe UI,Roboto,sans-serif;color:#1a202c;max-width:820px;margin:32px auto;padding:0 24px;}
  h1{font-size:20px;margin:0;} .sub{color:#64748b;font-size:12px;margin-bottom:24px;}
  .scores{display:flex;gap:24px;margin:16px 0 28px;align-items:center;}
  .ring{border:4px solid;border-radius:50%;width:92px;height:92px;display:flex;align-items:center;justify-content:center;font-size:24px;font-weight:700;}
  .ring.c-red{border-color:#f87171;color:#dc2626;} .ring.c-amber{border-color:#fbbf24;color:#d97706;} .ring.c-green{border-color:#34d399;color:#059669;}
  .grade{font-size:18px;font-weight:600;} .gsub{font-size:12px;color:#64748b;max-width:520px;}
  h2{font-size:14px;border-bottom:1px solid #e2e8f0;padding-bottom:6px;margin-top:28px;}
  table{width:100%;border-collapse:collapse;font-size:12px;} td{padding:8px;border-bottom:1px solid #eef2f7;vertical-align:top;}
  td.r{width:52px;font-weight:700;text-align:center;} .src{color:#94a3b8;font-size:11px;margin-top:3px;}
  ul{font-size:12px;padding-left:18px;} li{margin:6px 0;}
  footer{margin-top:40px;color:#94a3b8;font-size:11px;text-align:center;}
  @media print{body{margin:0;}}
</style></head><body>
<h1>Laporan Penilaian Esai</h1>
<div class="sub">ICALORA-LABS · MRH INNOVEX — dibuat ${esc(now)}</div>
<div class="scores">
  <div class="ring ${ringClass(res.overall_score ?? 0)}">${res.overall_score ?? "–"}</div>
  <div><div class="grade">Nilai ${esc(res.grade ?? "")}</div><div class="gsub">${esc(
      res.summary,
    )}</div></div>
</div>
${criteria ? `<h2>Penilaian per Kriteria</h2><table>${criteria}</table>` : ""}
${suggestions ? `<h2>Saran Perbaikan</h2><ul>${suggestions}</ul>` : ""}
<footer>Dinilai oleh ICALORA-LABS. Laporan ini bersifat indikatif untuk tinjauan akademik.</footer>
</body></html>`;
    const blob = new Blob([html], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `laporan-penilaian-${Date.now()}.html`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-4">
      <TextInput value={text} onChange={setText} rows={8} placeholder="Tempel esai yang ingin dinilai…" />
      <input
        value={rubric}
        onChange={(e) => setRubric(e.target.value)}
        placeholder="Rubrik khusus (opsional) — mis. 'fokus pada metodologi & sitasi'"
        className="w-full rounded-lg border border-c surface px-3 py-2 text-sm focus:border-[color:var(--brand)] focus:outline-none"
      />
      <button
        onClick={run}
        disabled={loading || !text.trim()}
        className="rounded-lg bg-[color:var(--brand)] px-5 py-2 text-sm font-medium text-white disabled:opacity-40"
      >
        {loading ? "Menilai…" : "Nilai Esai"}
      </button>
      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300">
          {error}
        </div>
      )}
      {res && (
        <div className="space-y-4">
          {res.overall_score !== null && (
            <div className="flex items-center gap-4 rounded-xl border border-c surface-2 p-5">
              <div
                className="flex h-20 w-20 items-center justify-center rounded-full text-2xl font-bold text-white"
                style={{ background: scoreColor(res.overall_score) }}
              >
                {res.overall_score}
              </div>
              <div>
                <div className="text-lg font-semibold">Nilai {res.grade ?? ""}</div>
                <p className="text-sm text-neutral-500 dark:text-neutral-400">{res.summary}</p>
              </div>
            </div>
          )}
          {res.criteria?.length > 0 && (
            <div className="grid gap-3 sm:grid-cols-2">
              {res.criteria.map((c, i) => (
                <div key={i} className="rounded-xl border border-c surface-2 p-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">{c.name}</span>
                    <span className="text-sm font-bold" style={{ color: scoreColor(c.score) }}>
                      {c.score}
                    </span>
                  </div>
                  <div className="mt-2 h-1.5 w-full rounded-full bg-neutral-200 dark:bg-neutral-800">
                    <div
                      className="h-1.5 rounded-full"
                      style={{ width: `${c.score}%`, background: scoreColor(c.score) }}
                    />
                  </div>
                  <p className="mt-2 text-xs text-neutral-500 dark:text-neutral-400">{c.feedback}</p>
                </div>
              ))}
            </div>
          )}
          {res.suggestions?.length > 0 && (
            <div className="rounded-xl border border-c surface-2 p-4">
              <div className="mb-2 text-xs font-medium uppercase tracking-wide text-neutral-400">
                Saran Perbaikan
              </div>
              <ul className="list-inside list-disc space-y-1 text-sm text-neutral-700 dark:text-neutral-300">
                {res.suggestions.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>
          )}
          <button
            onClick={downloadReport}
            className="rounded-lg border border-c surface-2 px-4 py-2 text-sm font-medium hover:bg-black/5 dark:hover:bg-white/5"
          >
            ⬇ Unduh laporan (HTML)
          </button>
        </div>
      )}
    </div>
  );
}
