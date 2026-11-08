"use client";

import { useState } from "react";
import { apiPost } from "@/lib/api";
import TextInput from "@/components/TextInput";
import { useJobLauncher } from "@/lib/useJobs";
import { jobTitle } from "@/lib/jobs";

export default function AuthorshipTool() {
  const [text, setText] = useState("");
  const [compare, setCompare] = useState("");
  const [showCompare, setShowCompare] = useState(false);
  const launch = useJobLauncher();

  function run() {
    if (!text.trim()) return;
    launch({
      tool: "authorship",
      title: jobTitle(text),
      run: () =>
        apiPost("/tools/authorship", {
          text,
          compare: showCompare && compare.trim() ? compare : null,
        }),
    });
  }

  return (
    <div className="space-y-4">
      <TextInput value={text} onChange={setText} rows={7} placeholder="Tempel teks untuk dianalisis gaya penulisannya…" />
      <label className="flex items-center gap-2 text-sm text-neutral-600 dark:text-neutral-400">
        <input type="checkbox" checked={showCompare} onChange={(e) => setShowCompare(e.target.checked)} />
        Bandingkan dengan teks kedua (cek kemungkinan penulis sama)
      </label>
      {showCompare && (
        <TextInput value={compare} onChange={setCompare} rows={6} placeholder="Tempel teks pembanding…" />
      )}
      <button
        onClick={run}
        disabled={!text.trim()}
        className="w-full rounded-xl bg-[color:var(--brand)] px-5 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-40"
      >
        Analisis Gaya
      </button>
    </div>
  );
}
