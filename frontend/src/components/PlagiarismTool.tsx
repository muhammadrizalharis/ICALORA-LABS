"use client";

import { useState } from "react";
import { apiPost } from "@/lib/api";
import TextInput from "@/components/TextInput";
import { useJobLauncher } from "@/lib/useJobs";
import { jobTitle } from "@/lib/jobs";

export default function PlagiarismTool() {
  const [text, setText] = useState("");
  const [docTitle, setDocTitle] = useState("");
  const launch = useJobLauncher();

  function run() {
    if (!text.trim()) return;
    launch({
      tool: "plagiarism-checker",
      title: docTitle.trim() || jobTitle(text),
      run: () => apiPost("/tools/plagiarism", { text, top_k: 30 }),
    });
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3 rounded-xl border border-c bg-[color:var(--brand-soft)] px-4 py-3 text-sm text-neutral-700 dark:text-neutral-200">
        <span className="text-lg">⏱️</span>
        <span>
          Proses pemeriksaan berlangsung singkat. Begitu kamu kirim, dokumen akan tampil di Beranda
          lengkap dengan status prosesnya, lalu hasil dapat dibuka saat selesai.
        </span>
      </div>

      <div>
        <label className="mb-1.5 block text-xs font-medium text-neutral-600 dark:text-neutral-300">
          Judul Dokumen (opsional)
        </label>
        <input
          value={docTitle}
          onChange={(e) => setDocTitle(e.target.value)}
          placeholder="Masukkan judul dokumen…"
          className="mb-3 w-full rounded-lg border border-c surface px-3 py-2 text-sm text-neutral-900 outline-none focus:border-[color:var(--brand)] dark:text-neutral-100 dark:placeholder:text-neutral-500"
        />
        <TextInput
          value={text}
          onChange={setText}
          placeholder="Tempel teks/abstrak, atau unggah berkas .pdf/.docx/.txt untuk diperiksa keasliannya…"
          rows={10}
        />
      </div>

      <div className="flex items-start gap-3 rounded-xl border border-c bg-[color:var(--brand-soft)] px-4 py-3">
        <span className="text-lg">✨</span>
        <div className="text-sm">
          <div className="font-semibold text-neutral-800 dark:text-neutral-100">
            Mesin pemeriksa: ICALORA Similarity Checker
          </div>
          <p className="mt-0.5 text-neutral-600 dark:text-neutral-300">
            Seluruh pencocokan dijalankan di infrastruktur milik ICALORA-LABS sendiri. Kamu akan
            menerima rincian sumber yang mirip serta penandaan bagian teks terkait, lengkap dengan
            filter bibliografi/kutipan yang bisa diatur saat membuka hasil.
          </p>
        </div>
      </div>

      <button
        onClick={run}
        disabled={text.trim().length === 0}
        className="w-full rounded-xl bg-[color:var(--brand)] px-5 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-40"
      >
        Periksa Kemiripan
      </button>
      <p className="text-center text-xs text-neutral-400 dark:text-neutral-500">
        Dibandingkan dengan korpus akses-terbuka ICALORA-LABS · laporan dapat diunduh sebagai PDF.
      </p>
    </div>
  );
}
