"use client";

import { useState } from "react";
import { apiPost } from "@/lib/api";
import TextInput from "@/components/TextInput";
import { useJobLauncher } from "@/lib/useJobs";
import { jobTitle } from "@/lib/jobs";

export default function HiddenTextTool() {
  const [text, setText] = useState("");
  const launch = useJobLauncher();

  function run() {
    if (!text.trim()) return;
    launch({
      tool: "hidden-text",
      title: jobTitle(text),
      run: () => apiPost("/tools/hidden-text", { text, check_typos: true }),
    });
  }

  return (
    <div className="space-y-4">
      <TextInput
        value={text}
        onChange={setText}
        rows={8}
        placeholder="Tempel teks (atau unggah dokumen) untuk memindai teks tersembunyi & typo…"
      />
      <button
        onClick={run}
        disabled={!text.trim()}
        className="w-full rounded-xl bg-[color:var(--brand)] px-5 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-40"
      >
        Pindai Dokumen
      </button>
    </div>
  );
}
