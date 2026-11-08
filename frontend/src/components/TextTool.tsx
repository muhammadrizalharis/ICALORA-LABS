"use client";

import { useState } from "react";
import { apiPost } from "@/lib/api";
import TextInput from "@/components/TextInput";
import { useJobLauncher } from "@/lib/useJobs";
import { jobTitle } from "@/lib/jobs";

type ToolKind = "word-count" | "text-output";

interface TextToolProps {
  endpoint: string;
  kind: ToolKind;
  slug: string;
  placeholder?: string;
  submitLabel?: string;
  outputKey?: string; // dipertahankan untuk kompatibilitas pemanggil
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
  slug,
  placeholder = "Tempel atau ketik teks di sini…",
  submitLabel = "Proses",
}: TextToolProps) {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [wc, setWc] = useState<WordCountResult | null>(null);
  const launch = useJobLauncher();

  async function handleSubmit() {
    if (!text.trim()) return;

    // Penghitung kata bersifat instan → tetap diproses & ditampilkan di tempat.
    if (kind === "word-count") {
      setLoading(true);
      setError(null);
      setWc(null);
      try {
        const data = await apiPost<Record<string, unknown>>(endpoint, { text });
        setWc(data as unknown as WordCountResult);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Terjadi kesalahan.");
      } finally {
        setLoading(false);
      }
      return;
    }

    // Tool lain: proses di latar, lalu arahkan ke Beranda.
    launch({
      tool: slug,
      title: jobTitle(text),
      run: () => apiPost<Record<string, unknown>>(endpoint, { text }),
    });
  }

  return (
    <div className="space-y-4">
      <TextInput value={text} onChange={setText} placeholder={placeholder} rows={8} />
      <button
        onClick={handleSubmit}
        disabled={loading || !text.trim()}
        className="w-full rounded-xl bg-[color:var(--brand)] px-5 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-40"
      >
        {loading ? "Memproses…" : submitLabel}
      </button>
      <p className="text-center text-xs text-neutral-400 dark:text-neutral-500">
        {text.length.toLocaleString("id-ID")} karakter
      </p>

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
    </div>
  );
}
