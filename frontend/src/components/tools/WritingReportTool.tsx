"use client";

import { useState } from "react";
import TextInput from "@/components/TextInput";
import { useJobLauncher } from "@/lib/useJobs";
import { jobTitle } from "@/lib/jobs";
import { submitGrammarFileJob, submitGrammarTextJob } from "@/lib/grammarJob";

type Mode = "text" | "pdf";

export default function WritingReportTool() {
  const [mode, setMode] = useState<Mode>("text");
  const [text, setText] = useState("");
  const [docTitle, setDocTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const launch = useJobLauncher();

  function run() {
    if (mode === "pdf") {
      if (!file || !docTitle.trim()) return;
      const original = file;
      launch({
        tool: "grammar-checker",
        title: docTitle.trim() || original.name,
        run: () => submitGrammarFileJob({ file: original }),
      });
    } else {
      if (!text.trim()) return;
      const value = text;
      launch({
        tool: "grammar-checker",
        title: jobTitle(value),
        run: () => submitGrammarTextJob({ text: value }),
      });
    }
  }

  const disabled = mode === "pdf" ? !file || docTitle.trim().length === 0 : !text.trim();

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3 rounded-xl border border-c bg-[color:var(--brand-soft)] px-4 py-3 text-sm text-neutral-700 dark:text-neutral-200">
        <span className="text-lg">⏱️</span>
        <span>
          Pemeriksaan berjalan di latar belakang server. Dokumen panjang dipecah per bagian dan
          diperiksa menyeluruh tanpa pemotongan — kamu boleh menutup halaman ini. Unggah PDF agar
          laporan berformat identik dengan sorotan masalah langsung di atas dokumen asli bisa
          diunduh.
        </span>
      </div>

      <div className="inline-flex rounded-xl border border-c p-1 text-sm">
        <button
          type="button"
          onClick={() => setMode("text")}
          className={`rounded-lg px-4 py-1.5 font-medium transition ${
            mode === "text"
              ? "bg-[color:var(--brand)] text-white"
              : "text-neutral-600 dark:text-neutral-300"
          }`}
        >
          Tempel Teks
        </button>
        <button
          type="button"
          onClick={() => setMode("pdf")}
          className={`rounded-lg px-4 py-1.5 font-medium transition ${
            mode === "pdf"
              ? "bg-[color:var(--brand)] text-white"
              : "text-neutral-600 dark:text-neutral-300"
          }`}
        >
          Unggah PDF
        </button>
      </div>

      {mode === "pdf" ? (
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
      ) : (
        <TextInput
          value={text}
          onChange={setText}
          rows={10}
          placeholder="Tempel teks untuk diperiksa tata bahasa & kualitas penulisannya…"
        />
      )}

      <button
        onClick={run}
        disabled={disabled}
        className="w-full rounded-xl bg-[color:var(--brand)] px-5 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-40"
      >
        Periksa Penulisan
      </button>
      <p className="text-center text-xs text-neutral-400 dark:text-neutral-500">
        Mesin ICALORA-LABS · laporan dapat diunduh sebagai PDF dengan sorotan masalah (merah =
        kritis, oranye = lanjutan) saat kamu mengunggah PDF.
      </p>
    </div>
  );
}
