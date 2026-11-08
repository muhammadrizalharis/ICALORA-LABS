"use client";

import { useState } from "react";
import { apiPost } from "@/lib/api";
import TextInput from "@/components/TextInput";
import { useJobLauncher } from "@/lib/useJobs";
import { jobTitle } from "@/lib/jobs";

const GOALS = ["", "lebih ringkas", "lebih formal/baku", "lebih jelas & runtut", "gaya akademik"];

export default function ImproveTool() {
  const [text, setText] = useState("");
  const [goal, setGoal] = useState("");
  const launch = useJobLauncher();

  function run() {
    if (!text.trim()) return;
    launch({
      tool: "perbaikan-dokumen",
      title: jobTitle(text),
      run: () => apiPost("/tools/improve", { text, goal: goal || null }),
    });
  }

  return (
    <div className="space-y-4">
      <TextInput
        value={text}
        onChange={setText}
        rows={8}
        placeholder="Tempel dokumen (atau unggah PDF/DOCX) yang ingin diperbaiki…"
      />
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-neutral-500 dark:text-neutral-400">Fokus:</span>
        {GOALS.map((g) => (
          <button
            key={g}
            onClick={() => setGoal(g)}
            className={`rounded-full border px-3 py-1 text-xs transition ${
              goal === g
                ? "border-[color:var(--brand)] bg-[color:var(--brand)] text-white"
                : "border-c text-neutral-600 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-900"
            }`}
          >
            {g || "otomatis"}
          </button>
        ))}
      </div>
      <button
        onClick={run}
        disabled={!text.trim()}
        className="w-full rounded-xl bg-[color:var(--brand)] px-5 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-40"
      >
        Perbaiki Dokumen
      </button>
    </div>
  );
}
