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
}

const ACCEPT = ".txt,.md,.csv,.tex,.pdf,.docx";

export default function TextInput({
  value,
  onChange,
  placeholder = "Tempel atau ketik teks di sini…",
  rows = 8,
}: TextInputProps) {
  const [mode, setMode] = useState<"paste" | "upload">("paste");
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [fileInfo, setFileInfo] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleFile(file: File) {
    setErr(null);
    setUploading(true);
    try {
      const res = await apiUpload<ExtractResult>("/tools/extract-text", file);
      onChange(res.text);
      setFileInfo(`${res.filename} · ${res.chars.toLocaleString("id-ID")} karakter diekstrak`);
      setMode("paste");
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

      {mode === "paste" ? (
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
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
            accept={ACCEPT}
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
            Mendukung .txt, .pdf, .docx (maks 10 MB)
          </div>
        </div>
      )}

      {fileInfo && mode === "paste" && (
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
