"use client";

import { useState } from "react";
import { apiPost } from "@/lib/api";
import TextInput from "@/components/TextInput";
import { useJobLauncher } from "@/lib/useJobs";
import { jobTitle } from "@/lib/jobs";

export default function ReactionsTool() {
  const [text, setText] = useState("");
  const launch = useJobLauncher();

  function run() {
    if (!text.trim()) return;
    launch({
      tool: "reader-reactions",
      title: jobTitle(text),
      run: () => apiPost("/tools/reader-reactions", { text }),
    });
  }

  return (
    <div className="space-y-4">
      <TextInput value={text} onChange={setText} rows={8} placeholder="Tempel teks untuk diprediksi reaksi pembacanya…" />
      <button
        onClick={run}
        disabled={!text.trim()}
        className="w-full rounded-xl bg-[color:var(--brand)] px-5 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-40"
      >
        Prediksi Reaksi
      </button>
    </div>
  );
}
