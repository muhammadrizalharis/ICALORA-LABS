"use client";

import { useState } from "react";
import { apiPost } from "@/lib/api";
import TextInput from "@/components/TextInput";
import { useJobLauncher } from "@/lib/useJobs";
import { jobTitle } from "@/lib/jobs";

export default function GraderTool() {
  const [text, setText] = useState("");
  const [rubric, setRubric] = useState("");
  const launch = useJobLauncher();

  function run() {
    if (!text.trim()) return;
    launch({
      tool: "ai-grader",
      title: jobTitle(text),
      run: () => apiPost("/tools/grade", { text, rubric: rubric.trim() || null }),
    });
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
        disabled={!text.trim()}
        className="w-full rounded-xl bg-[color:var(--brand)] px-5 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-40"
      >
        Nilai Esai
      </button>
    </div>
  );
}
