"use client";

import { useState } from "react";
import TextInput from "@/components/TextInput";
import { useJobLauncher } from "@/lib/useJobs";
import { jobTitle } from "@/lib/jobs";
import { submitPlagiarismJob } from "@/lib/plagiarismJob";

export default function PlagiarismTool() {
  const [text, setText] = useState("");
  const [docTitle, setDocTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [exBib, setExBib] = useState(true);
  const [exQuotes, setExQuotes] = useState(true);
  const [exMatches, setExMatches] = useState(false);
  const [exMinPct, setExMinPct] = useState("1");
  const launch = useJobLauncher();

  function run() {
    if (!text.trim() || !docTitle.trim()) return;
    const original = file;
    const minPct = exMatches ? Math.max(0, Math.min(100, parseFloat(exMinPct) || 0)) : 0;
    launch({
      tool: "plagiarism-checker",
      title: docTitle.trim() || (original ? original.name : jobTitle(text)),
      run: () =>
        submitPlagiarismJob({
          text,
          file: original,
          topK: 30,
          exclude: {
            bibliography: exBib,
            quotes: exQuotes,
            min_source_percent: minPct,
          },
        }),
    });
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3 rounded-xl border border-c bg-[color:var(--brand-soft)] px-4 py-3 text-sm text-neutral-700 dark:text-neutral-200">
        <span className="text-lg">⏱️</span>
        <span>
          Pemeriksaan berjalan di latar belakang server. Begitu kamu kirim, dokumen tampil di
          Beranda dengan status prosesnya — kamu boleh menutup halaman ini; hasil dapat dibuka saat
          proses selesai (termasuk pencocokan ke ratusan sumber daring).
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
          value={text}
          onChange={setText}
          onFile={setFile}
          placeholder="Tempel teks/abstrak, atau unggah berkas .pdf/.docx/.txt untuk diperiksa keasliannya…"
          rows={10}
        />
      </div>

      <div className="rounded-xl border border-c bg-neutral-50 px-4 py-3 dark:bg-white/5">
        <div className="mb-0.5 text-xs font-semibold text-neutral-700 dark:text-neutral-200">
          Pengaturan Exclude
        </div>
        <p className="mb-2.5 text-[11px] text-neutral-400">
          Dipilih sebelum pemeriksaan dan <span className="font-medium">dikunci</span> pada hasil —
          tidak bisa diubah setelah cek berjalan.
        </p>
        <div className="space-y-2 text-xs text-neutral-600 dark:text-neutral-300">
          <label className="flex cursor-pointer items-center gap-2">
            <input type="checkbox" checked={exBib} onChange={(e) => setExBib(e.target.checked)} />
            Tanpa daftar pustaka
          </label>
          <label className="flex cursor-pointer items-center gap-2">
            <input
              type="checkbox"
              checked={exQuotes}
              onChange={(e) => setExQuotes(e.target.checked)}
            />
            Tanpa kutipan
          </label>
          <label className="flex cursor-pointer items-center gap-2">
            <input
              type="checkbox"
              checked={exMatches}
              onChange={(e) => setExMatches(e.target.checked)}
            />
            Kecualikan kecocokan dari sumber yang menyumbang kurang dari
            <input
              type="number"
              min={0}
              max={100}
              step="0.1"
              value={exMinPct}
              disabled={!exMatches}
              onChange={(e) => setExMinPct(e.target.value)}
              className="w-16 rounded border border-c surface px-2 py-1 text-center text-xs outline-none focus:border-[color:var(--brand)] disabled:opacity-40"
            />
            %
          </label>
        </div>
      </div>

      <button
        onClick={run}
        disabled={text.trim().length === 0 || docTitle.trim().length === 0}
        className="w-full rounded-xl bg-[color:var(--brand)] px-5 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-40"
      >
        Periksa Kemiripan
      </button>
      <p className="text-center text-xs text-neutral-400 dark:text-neutral-500">
        Dibandingkan dengan korpus akses-terbuka ICALORA-LABS · laporan dapat diunduh sebagai PDF.
      </p>

      <div className="flex items-start gap-3 rounded-xl border border-c bg-[color:var(--brand-soft)] px-4 py-3">
        <span className="text-lg">✨</span>
        <div className="text-sm">
          <div className="font-semibold text-neutral-800 dark:text-neutral-100">
            Mesin pemeriksa: ICALORA Similarity Checker
          </div>
          <p className="mt-0.5 text-neutral-600 dark:text-neutral-300">
            Seluruh pencocokan dijalankan di infrastruktur milik ICALORA-LABS sendiri. Kamu akan
            menerima rincian sumber yang mirip serta penandaan bagian teks terkait, sesuai
            pengaturan Exclude yang kamu pilih sebelum pemeriksaan.
          </p>
        </div>
      </div>
    </div>
  );
}
