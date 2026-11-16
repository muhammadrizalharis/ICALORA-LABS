"use client";

import { useState } from "react";
import TextInput from "@/components/TextInput";
import { useJobLauncher } from "@/lib/useJobs";
import { jobTitle } from "@/lib/jobs";
import { submitTransformFileJob, submitTransformTextJob } from "@/lib/transformJob";

type OptionValue = { value: string; label: string };

export interface TransformToolProps {
  tool: string;
  textPath: string;
  filePath: string;
  submitLabel: string;
  textPlaceholder: string;
  /** Nama field opsi yang dikirim (mis. "style", "tone", "goal"). */
  optionField?: string;
  optionLabel?: string;
  optionKind?: "select" | "chips";
  optionValues?: OptionValue[];
  optionDefault?: string;
}

type Mode = "text" | "pdf";

export default function TransformTool(props: TransformToolProps) {
  const {
    tool, textPath, filePath, submitLabel, textPlaceholder,
    optionField, optionLabel, optionKind = "select", optionValues = [],
    optionDefault = "",
  } = props;

  const [mode, setMode] = useState<Mode>("text");
  const [text, setText] = useState("");
  const [docTitle, setDocTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [option, setOption] = useState(optionDefault);
  const launch = useJobLauncher();

  function run() {
    if (mode === "pdf") {
      if (!file || !docTitle.trim()) return;
      const original = file;
      const fields = optionField ? { [optionField]: option } : undefined;
      launch({
        tool,
        title: docTitle.trim() || original.name,
        run: () => submitTransformFileJob(filePath, original, fields),
      });
    } else {
      if (!text.trim()) return;
      const value = text;
      const body: Record<string, unknown> = { text: value };
      if (optionField) body[optionField] = option;
      launch({
        tool,
        title: jobTitle(value),
        run: () => submitTransformTextJob(textPath, body),
      });
    }
  }

  const disabled = mode === "pdf" ? !file || docTitle.trim().length === 0 : !text.trim();

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3 rounded-xl border border-c bg-[color:var(--brand-soft)] px-4 py-3 text-sm text-neutral-700 dark:text-neutral-200">
        <span className="text-lg">⏱️</span>
        <span>
          Diproses di latar belakang server. Dokumen panjang dipecah per bagian dan diolah
          menyeluruh tanpa pemotongan — kamu boleh menutup halaman ini. Unggah PDF agar laporan
          perbandingan (asli vs hasil, dengan sorotan perubahan) bisa diunduh.
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

      {optionField && (
        <div className="flex flex-wrap items-center gap-2">
          {optionLabel && (
            <span className="text-sm text-neutral-500 dark:text-neutral-400">{optionLabel}:</span>
          )}
          {optionKind === "select" ? (
            <select
              value={option}
              onChange={(e) => setOption(e.target.value)}
              className="rounded-lg border border-c surface px-3 py-2 text-sm"
            >
              {optionValues.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          ) : (
            optionValues.map((o) => (
              <button
                key={o.value}
                type="button"
                onClick={() => setOption(o.value)}
                className={`rounded-full border px-3 py-1 text-xs transition ${
                  option === o.value
                    ? "border-[color:var(--brand)] bg-[color:var(--brand)] text-white"
                    : "border-c text-neutral-600 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-900"
                }`}
              >
                {o.label}
              </button>
            ))
          )}
        </div>
      )}

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
            acceptHint="Hanya PDF (maks 10 MB) — agar laporan perbandingan bisa dibuat"
            rows={10}
          />
        </div>
      ) : (
        <TextInput value={text} onChange={setText} rows={10} placeholder={textPlaceholder} />
      )}

      <button
        onClick={run}
        disabled={disabled}
        className="w-full rounded-xl bg-[color:var(--brand)] px-5 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-40"
      >
        {submitLabel}
      </button>
    </div>
  );
}
