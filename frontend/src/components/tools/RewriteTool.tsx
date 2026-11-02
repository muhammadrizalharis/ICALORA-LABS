"use client";

import { useState } from "react";
import { apiPost } from "@/lib/api";
import TextInput from "@/components/TextInput";

const TONES: { value: string; label: string }[] = [
  { value: "formal", label: "Formal" },
  { value: "akademik", label: "Akademik" },
  { value: "kasual", label: "Kasual" },
  { value: "ringkas", label: "Ringkas" },
  { value: "persuasif", label: "Persuasif" },
  { value: "sederhana", label: "Sederhana" },
];

export default function RewriteTool() {
  const [text, setText] = useState("");
  const [tone, setTone] = useState("formal");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [out, setOut] = useState<string | null>(null);

  async function run() {
    if (!text.trim()) return;
    setLoading(true);
    setError(null);
    setOut(null);
    try {
      const d = await apiPost<{ result: string }>("/tools/rewrite", { text, tone });
      setOut(d.result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Terjadi kesalahan.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <TextInput value={text} onChange={setText} rows={8} placeholder="Tempel teks yang ingin ditulis ulang…" />
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-sm text-neutral-500 dark:text-neutral-400">Gaya:</label>
        <select
          value={tone}
          onChange={(e) => setTone(e.target.value)}
          className="rounded-lg border border-c surface px-3 py-2 text-sm"
        >
          {TONES.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>
        <button
          onClick={run}
          disabled={loading || !text.trim()}
          className="rounded-lg bg-[color:var(--brand)] px-5 py-2 text-sm font-medium text-white disabled:opacity-40"
        >
          {loading ? "Memproses…" : "Tulis Ulang"}
        </button>
      </div>
      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300">
          {error}
        </div>
      )}
      {out !== null && (
        <div className="rounded-xl border border-c surface-2 p-4">
          <div className="mb-2 text-xs font-medium uppercase tracking-wide text-neutral-400">Hasil</div>
          <p className="whitespace-pre-wrap text-sm text-neutral-900 dark:text-neutral-100">{out}</p>
        </div>
      )}
    </div>
  );
}
