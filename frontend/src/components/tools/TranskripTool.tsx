"use client";

import { useRef, useState } from "react";
import { API_BASE } from "@/lib/api";
import { useJobLauncher } from "@/lib/useJobs";

const ACCEPT = ".mp3,.wav,.m4a,.ogg,.flac,.aac,.opus,.mp4,.webm,.mkv,.mov,.wma";

export default function TranskripTool() {
  const [fileName, setFileName] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const launch = useJobLauncher();

  function handleFile(file: File) {
    setFileName(file.name);
    launch({
      tool: "transkrip-audio",
      title: file.name,
      run: async () => {
        const form = new FormData();
        form.append("file", file);
        const r = await fetch(`${API_BASE}/tools/transcribe`, {
          method: "POST",
          body: form,
          cache: "no-store",
        });
        if (!r.ok) {
          let detail = `${r.status}`;
          try {
            const err = await r.json();
            if (err?.detail) detail = err.detail;
          } catch {
            /* abaikan */
          }
          throw new Error(detail);
        }
        return r.json();
      },
    });
  }

  return (
    <div className="space-y-4">
      <div
        onClick={() => fileRef.current?.click()}
        className="cursor-pointer rounded-xl border border-dashed border-c surface-2 p-6 text-center transition hover:border-[color:var(--brand)]"
      >
        <input
          ref={fileRef}
          type="file"
          accept={ACCEPT}
          className="hidden"
          onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
        />
        {fileName ? (
          <span className="text-sm text-emerald-600 dark:text-emerald-400">🎧 {fileName}</span>
        ) : (
          <span className="text-sm text-neutral-500 dark:text-neutral-400">
            Klik untuk unggah audio/video (mp3, wav, m4a, mp4, …) — maks 50 MB.
          </span>
        )}
      </div>
    </div>
  );
}
