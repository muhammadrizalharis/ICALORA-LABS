"use client";

import { useRef, useState } from "react";
import { apiUpload } from "@/lib/api";

interface ExtractResult {
  filename: string;
  text: string;
  chars: number;
}

interface TextInputProps {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  rows?: number;
  /** Dipanggil dengan berkas asli saat diunggah (null bila pengguna mengetik/menempel). */
  onFile?: (file: File | null) => void;
  /** Daftar ekstensi yang diterima (mis. ".pdf"). Default: txt/pdf/docx. */
  accept?: string;
  /** Teks bantuan format di area unggah. */
  acceptHint?: string;
  /** Bila true: sembunyikan tab & mode tempel teks — hanya unggah berkas. */
  uploadOnly?: boolean;
}

const ACCEPT = ".txt,.md,.csv,.tex,.pdf,.docx";

export default function TextInput({
  value,
  onChange,
  placeholder = "Tempel atau ketik teks di sini…",
  rows = 8,
  onFile,
  accept = ACCEPT,
  acceptHint = "Mendukung .txt, .pdf, .docx (maks 10 MB)",
  uploadOnly = false,
}: TextInputProps) {
  const [mode, setMode] = useState<"paste" | "upload">(uploadOnly ? "upload" : "paste");
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [fileInfo, setFileInfo] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleFile(file: File) {
    setErr(null);
    const exts = accept
      .split(",")
      .map((s) => s.trim().toLowerCase())
      .filter(Boolean);
    const name = file.name.toLowerCase();
    if (exts.length && !exts.some((ext) => name.endsWith(ext))) {
      setErr(
        `Format tidak didukung. Hanya menerima: ${exts.join(", ")}.` +
          (exts.length === 1 && exts[0] === ".pdf"
            ? " Simpan dokumen Word Anda sebagai PDF lalu unggah ulang."
            : ""),
      );
      return;
    }
    setUploading(true);
    try {
      const res = await apiUpload<ExtractResult>("/tools/extract-text", file);
      onChange(res.text);
      onFile?.(file);
      setFileInfo(`${res.filename} · ${res.chars.toLocaleString("id-ID")} karakter diekstrak`);
      if (!uploadOnly) setMode("paste");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Gagal mengunggah berkas.");
    } finally {
      setUploading(false);
    }
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  }

  return (
    <div className="space-y-2">
      {/* Tab */}
      {!uploadOnly && (
        <div className="inline-flex rounded-lg border border-c p-0.5 text-sm">
          <button
            type="button"
            onClick={() => setMode("paste")}
            className={`rounded-md px-3 py-1.5 font-medium transition ${
              mode === "paste"
                ? "bg-[color:var(--brand)] text-white"
                : "text-neutral-600 hover:text-neutral-900 dark:text-neutral-300 dark:hover:text-white"
            }`}
          >
            ✍️ Tempel Teks
          </button>
          <button
            type="button"
            onClick={() => setMode("upload")}
            className={`rounded-md px-3 py-1.5 font-medium transition ${
              mode === "upload"
                ? "bg-[color:var(--brand)] text-white"
                : "text-neutral-600 hover:text-neutral-900 dark:text-neutral-300 dark:hover:text-white"
            }`}
          >
            📎 Unggah Berkas
          </button>
        </div>
      )}

      {mode === "paste" ? (
        <textarea
          value={value}
          onChange={(e) => {
            onChange(e.target.value);
            onFile?.(null);
          }}
          placeholder={placeholder}
          rows={rows}
          className="w-full resize-y rounded-xl border border-c surface p-4 text-sm text-neutral-900 outline-none focus:border-[color:var(--brand)] dark:text-neutral-100 dark:placeholder:text-neutral-500"
        />
      ) : (
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
          className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed p-10 text-center transition ${
            dragOver
              ? "border-[color:var(--brand)] bg-[color:var(--brand-soft)]"
              : "border-c surface hover:border-[color:var(--brand)]"
          }`}
        >
          <input
            ref={inputRef}
            type="file"
            accept={accept}
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) handleFile(f);
              e.target.value = "";
            }}
          />
          <span className="text-3xl">{uploading ? "⏳" : "📄"}</span>
          <div className="text-sm font-medium text-neutral-800 dark:text-neutral-200">
            {uploading ? "Mengekstrak teks…" : "Seret berkas ke sini atau klik untuk pilih"}
          </div>
          <div className="text-xs text-neutral-500 dark:text-neutral-400">
            {acceptHint}
          </div>
        </div>
      )}

      {fileInfo && (mode === "paste" || uploadOnly) && (
        <div className="flex items-center gap-2 text-xs text-emerald-600 dark:text-emerald-400">
          <span>✅</span> {fileInfo}
        </div>
      )}
      {err && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-2.5 text-xs text-rose-700 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300">
          {err}
        </div>
      )}
    </div>
  );
}
