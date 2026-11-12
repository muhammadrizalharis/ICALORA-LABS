"use client";

import { useState } from "react";
import { apiPost } from "@/lib/api";
import { useJobLauncher } from "@/lib/useJobs";
import { jobTitle } from "@/lib/jobs";
import TextInput from "@/components/TextInput";

export default function ResumeTool() {
  const [info, setInfo] = useState("");
  const [role, setRole] = useState("");
  const launch = useJobLauncher();

  function run() {
    if (!info.trim()) return;
    launch({
      tool: "resume-builder",
      title: role.trim() ? `CV · ${role.trim()}` : jobTitle(info),
      run: () => apiPost("/tools/resume", { info, target_role: role.trim() || null }),
    });
  }

  return (
    <div className="space-y-4">
      <TextInput
        value={info}
        onChange={setInfo}
        rows={8}
        placeholder="Masukkan data Anda: nama, kontak, pendidikan, pengalaman, keahlian, dsb. (bebas, satu per baris)"
      />
      <input
        value={role}
        onChange={(e) => setRole(e.target.value)}
        placeholder="Target posisi (opsional) — mis. 'Data Analyst'"
        className="w-full rounded-lg border border-c surface px-3 py-2 text-sm focus:border-[color:var(--brand)] focus:outline-none"
      />
      <button
        onClick={run}
        disabled={!info.trim()}
        className="w-full rounded-xl bg-[color:var(--brand)] px-5 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-40"
      >
        Susun CV
      </button>
    </div>
  );
}
