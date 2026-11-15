"use client";

import { useState } from "react";
import TextInput from "@/components/TextInput";
import { useJobLauncher } from "@/lib/useJobs";
import { submitAiDetectorJob } from "@/lib/aiDetectorJob";

export default function AiDetectorTool() {
  const [docTitle, setDocTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const launch = useJobLauncher();

  function run() {
    if (!file || !docTitle.trim()) return;
    const original = file;
    launch({
      tool: "ai-detector",
      title: docTitle.trim() || original.name,
      run: () => submitAiDetectorJob({ file: original }),
    });
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3 rounded-xl border border-c bg-[color:var(--brand-soft)] px-4 py-3 text-sm text-neutral-700 dark:text-neutral-200">
        <span className="text-lg">⏱️</span>
        <span>
          Deteksi berjalan di latar belakang server. Seluruh isi dokumen dianalisis tanpa
          pemotongan; laporan PDF berformat identik dengan berkas asli (sorotan per segmen) dapat
          diunduh saat proses selesai — kamu boleh menutup halaman ini.
        </span>
      </div>

      <div>
        <label className="mb-1.5 block text-xs font-medium text-neutral-600 dark:text-neutral-300">
          Judul Dokumen <span className="text-[color:var(--brand)]">*</span>
        </label>
        <input
          value={docTitle}
          onChange={(e) => setDocTitle(e.target.value)}
          placeholder="Masukkan judul dokumen…"
          required
          className="mb-3 w-full rounded-lg border border-c surface px-3 py-2 text-sm text-neutral-900 outline-none focus:border-[color:var(--brand)] dark:text-neutral-100 dark:placeholder:text-neutral-500"
        />
        <TextInput
          value=""
          onChange={() => {}}
          onFile={setFile}
          uploadOnly
          accept=".pdf"
          acceptHint="Hanya PDF (maks 10 MB) — agar laporan berformat identik dengan sorotan bisa dibuat"
          rows={10}
        />
      </div>

      <button
        onClick={run}
        disabled={!file || docTitle.trim().length === 0}
        className="w-full rounded-xl bg-[color:var(--brand)] px-5 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-40"
      >
        Deteksi AI
      </button>
      <p className="text-center text-xs text-neutral-400 dark:text-neutral-500">
        Mesin deteksi ICALORA-LABS · laporan dapat diunduh sebagai PDF dengan sorotan segmen
        (merah = AI, kuning = campuran, hijau = manusia).
      </p>

      <div className="flex items-start gap-3 rounded-xl border border-c bg-[color:var(--brand-soft)] px-4 py-3">
        <span className="text-lg">✨</span>
        <div className="text-sm">
          <div className="font-semibold text-neutral-800 dark:text-neutral-100">
            Mesin deteksi: ICALORA AI Detector
          </div>
          <p className="mt-0.5 text-neutral-600 dark:text-neutral-300">
            Seluruh analisis dijalankan di infrastruktur milik ICALORA-LABS sendiri. Kamu akan
            menerima probabilitas AI, komposisi teks (AI / campuran / manusia), serta penandaan
            bagian teks terkait langsung di atas dokumen asli.
          </p>
        </div>
      </div>
    </div>
  );
}
