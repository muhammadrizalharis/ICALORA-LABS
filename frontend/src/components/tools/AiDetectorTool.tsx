"use client";

import { useState } from "react";
import { apiPost } from "@/lib/api";
import TextInput from "@/components/TextInput";

interface Signals {
  burstiness: number;
  type_token_ratio: number;
  avg_sentence_length: number;
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
  note: string;
}

function probColor(p: number): string {
  if (p >= 70) return "#ef4444";
  if (p >= 45) return "#eab308";
  return "#22c55e";
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
              ["Jumlah kata", res.signals.word_count],
            ].map(([l, v]) => (
              <div key={l as string} className="rounded-xl border border-c surface-2 p-4">
                <div className="text-lg font-semibold">{v}</div>
                <div className="text-xs text-neutral-500 dark:text-neutral-400">{l}</div>
              </div>
            ))}
          </div>
          <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-300">
            ⚠️ {res.note}
          </p>
        </div>
      )}
    </div>
  );
}
