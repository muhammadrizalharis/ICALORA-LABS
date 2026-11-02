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
        </div>
      )}
    </div>
  );
}
