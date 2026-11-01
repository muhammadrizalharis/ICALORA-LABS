"use client";

import { useState } from "react";
import { apiPost } from "@/lib/api";

type ToolKind = "word-count" | "text-output";

interface TextToolProps {
  endpoint: string;
  kind: ToolKind;
  placeholder?: string;
  submitLabel?: string;
  outputKey?: string; // untuk kind "text-output": kunci field hasil
}

interface WordCountResult {
  characters: number;
  characters_no_spaces: number;
  words: number;
  sentences: number;
  paragraphs: number;
  reading_time_seconds: number;
  speaking_time_seconds: number;
}

function fmtTime(seconds: number): string {
  if (seconds < 60) return `${seconds} dtk`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return s ? `${m} mnt ${s} dtk` : `${m} mnt`;
}

export default function TextTool({
  endpoint,
  kind,
  placeholder = "Tempel atau ketik teks di sini…",
  submitLabel = "Proses",
  outputKey = "result",
}: TextToolProps) {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [wc, setWc] = useState<WordCountResult | null>(null);
  const [out, setOut] = useState<string | null>(null);

  async function handleSubmit() {
    if (!text.trim()) return;
    setLoading(true);
    setError(null);
    setWc(null);
    setOut(null);
    try {
      const data = await apiPost<Record<string, unknown>>(endpoint, { text });
      if (kind === "word-count") {
        setWc(data as unknown as WordCountResult);
      } else {
        setOut(String(data[outputKey] ?? ""));
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Terjadi kesalahan.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={placeholder}
        rows={8}
        className="w-full resize-y rounded-xl border border-c p-4 text-sm text-neutral-900 outline-none focus:border-neutral-500 dark:text-neutral-100 dark:placeholder:text-neutral-500 dark:focus:border-neutral-500"
      />
      <div className="flex items-center gap-3">
        <button
          onClick={handleSubmit}
          disabled={loading || !text.trim()}
          className="rounded-lg bg-neutral-900 px-5 py-2 text-sm font-medium text-white disabled:opacity-40 dark:bg-neutral-100 dark:text-neutral-900"
        >
          {loading ? "Memproses…" : submitLabel}
        </button>
        <span className="text-xs text-neutral-400 dark:text-neutral-500">{text.length} karakter</span>
      </div>

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300">
          {error}
        </div>
      )}

      {wc && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            ["Kata", wc.words],
            ["Karakter", wc.characters],
            ["Tanpa spasi", wc.characters_no_spaces],
            ["Kalimat", wc.sentences],
            ["Paragraf", wc.paragraphs],
            ["Waktu baca", fmtTime(wc.reading_time_seconds)],
            ["Waktu bicara", fmtTime(wc.speaking_time_seconds)],
          ].map(([label, value]) => (
            <div
              key={label as string}
              className="rounded-xl border border-c surface-2 p-4"
            >
              <div className="text-lg font-semibold text-neutral-900 dark:text-neutral-100">{value}</div>
              <div className="text-xs text-neutral-500 dark:text-neutral-400">{label}</div>
            </div>
          ))}
        </div>
      )}

      {out !== null && (
        <div className="rounded-xl border border-c surface-2 p-4">
          <div className="mb-2 text-xs font-medium uppercase tracking-wide text-neutral-400 dark:text-neutral-500">
            Hasil
          </div>
          <p className="whitespace-pre-wrap text-sm text-neutral-900 dark:text-neutral-100">{out}</p>
        </div>
      )}
    </div>
  );
}
