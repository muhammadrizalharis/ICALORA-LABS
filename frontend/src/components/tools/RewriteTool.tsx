"use client";

import { useState } from "react";
import { apiPost } from "@/lib/api";
import TextInput from "@/components/TextInput";
import { useJobLauncher } from "@/lib/useJobs";
import { jobTitle } from "@/lib/jobs";

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
  const launch = useJobLauncher();

  function run() {
    if (!text.trim()) return;
    launch({
      tool: "ai-rewriter",
      title: jobTitle(text),
      run: () => apiPost("/tools/rewrite", { text, tone }),
    });
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
      </div>
      <button
        onClick={run}
        disabled={!text.trim()}
        className="w-full rounded-xl bg-[color:var(--brand)] px-5 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-40"
      >
        Tulis Ulang
      </button>
    </div>
  );
}
