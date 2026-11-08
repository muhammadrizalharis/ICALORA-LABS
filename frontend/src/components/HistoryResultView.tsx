"use client";

import Link from "next/link";
import { getFeature } from "@/lib/features";

export interface HistoryItemFull {
  id: number;
  tool: string;
  title: string | null;
  input_preview: string | null;
  result: Record<string, unknown> | null;
  created_at: string | null;
}

function fmtDate(iso: string | null): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleString("id-ID", { dateStyle: "long", timeStyle: "short" });
  } catch {
    return iso;
  }
}

function Ring({ value, label }: { value: number; label: string }) {
  const pct = Math.max(0, Math.min(100, Math.round(value)));
  const tone =
    pct >= 50 ? "#ef4444" : pct >= 25 ? "#f59e0b" : "var(--brand)";
  return (
    <div className="flex flex-col items-center">
      <div
        className="grid h-28 w-28 place-items-center rounded-full"
        style={{ background: `conic-gradient(${tone} ${pct * 3.6}deg, var(--brand-soft) 0deg)` }}
      >
        <div className="grid h-20 w-20 place-items-center rounded-full surface">
          <span className="text-xl font-bold" style={{ color: tone }}>
            {pct}%
          </span>
        </div>
      </div>
      <span className="mt-2 text-xs text-neutral-500 dark:text-neutral-400">{label}</span>
    </div>
  );
}

const SCORE_KEYS: { key: string; label: string }[] = [
  { key: "overall_similarity", label: "Indeks Kemiripan" },
  { key: "similarity_index", label: "Indeks Kemiripan" },
  { key: "ai_percentage", label: "Terdeteksi AI" },
  { key: "ai_score", label: "Terdeteksi AI" },
  { key: "score", label: "Skor" },
];

const TEXT_KEYS = [
  "result",
  "text",
  "corrected",
  "output",
  "answer",
  "reply",
  "transcript",
  "toc",
  "markdown",
  "summary",
  "resume",
];

const LABELS: Record<string, string> = {
  summary: "Ringkasan",
  corrected: "Teks Terkoreksi",
  result: "Hasil",
  text: "Hasil",
  transcript: "Transkrip",
  toc: "Daftar Isi",
  answer: "Jawaban",
  reply: "Balasan",
  resume: "Resume",
  markdown: "Hasil",
  output: "Hasil",
};

function isNumericScore(v: unknown): v is number {
  return typeof v === "number" && v >= 0 && v <= 100;
}

export default function HistoryResultView({ item }: { item: HistoryItemFull }) {
  const feature = getFeature(item.tool);
  const result = item.result ?? {};

  const scoreEntry = SCORE_KEYS.find(
    (s) => s.key in result && typeof result[s.key] === "number",
  );
  const scoreValue = scoreEntry ? (result[scoreEntry.key] as number) : null;

  const textSections = TEXT_KEYS.filter(
    (k) => typeof result[k] === "string" && (result[k] as string).trim().length > 0,
  );

  const metricEntries: [string, number][] = Object.entries(result)
    .filter(
      ([k, v]) =>
        isNumericScore(v) && k !== scoreEntry?.key && !k.toLowerCase().includes("count"),
    )
    .map(([k, v]) => [k, v as number]);

  const sources = Array.isArray(result.sources)
    ? (result.sources as Record<string, unknown>[])
    : [];

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-2xl">{feature?.icon ?? "📄"}</span>
            <h1 className="truncate text-xl font-bold text-neutral-900 dark:text-neutral-50">
              {item.title ?? feature?.name ?? item.tool}
            </h1>
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-neutral-400">
            <span className="rounded-full border border-c px-2 py-0.5">
              {feature?.name ?? item.tool}
            </span>
            <span>{fmtDate(item.created_at)}</span>
            <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 font-medium text-emerald-600 dark:text-emerald-400">
              Selesai
            </span>
          </div>
        </div>
        {feature && (
          <Link
            href={`/dashboard/tools/${item.tool}`}
            className="shrink-0 rounded-lg bg-[color:var(--brand)] px-4 py-2 text-sm font-medium text-white hover:opacity-90"
          >
            Periksa ulang
          </Link>
        )}
      </div>

      {(scoreValue !== null || metricEntries.length > 0) && (
        <div className="flex flex-wrap items-center gap-6 rounded-xl border border-c surface-2 p-5">
          {scoreValue !== null && scoreEntry && (
            <Ring value={scoreValue} label={scoreEntry.label} />
          )}
          <div className="flex flex-wrap gap-3">
            {metricEntries.map(([k, v]) => (
              <div key={k} className="rounded-lg border border-c surface px-4 py-2">
                <div className="text-lg font-semibold text-neutral-900 dark:text-neutral-100">
                  {Math.round(v)}%
                </div>
                <div className="text-[11px] text-neutral-400">{k.replace(/_/g, " ")}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {item.input_preview && (
        <div className="rounded-xl border border-c surface-2 p-4">
          <div className="mb-1 text-xs font-medium text-neutral-500 dark:text-neutral-400">
            Cuplikan Dokumen
          </div>
          <p className="whitespace-pre-wrap text-sm text-neutral-700 dark:text-neutral-300">
            {item.input_preview}
          </p>
        </div>
      )}

      {textSections.map((k) => (
        <div key={k} className="rounded-xl border border-c surface-2 p-4">
          <div className="mb-2 text-xs font-medium text-neutral-500 dark:text-neutral-400">
            {LABELS[k] ?? k}
          </div>
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-neutral-800 dark:text-neutral-200">
            {result[k] as string}
          </p>
        </div>
      ))}

      {sources.length > 0 && (
        <div className="rounded-xl border border-c surface-2 p-4">
          <div className="mb-2 text-xs font-medium text-neutral-500 dark:text-neutral-400">
            Sumber Terkait ({sources.length})
          </div>
          <ul className="space-y-2">
            {sources.slice(0, 20).map((s, i) => {
              const sim = typeof s.similarity === "number" ? s.similarity : null;
              return (
                <li key={i} className="text-sm text-neutral-700 dark:text-neutral-300">
                  <span className="font-medium">
                    {(s.title as string) ?? (s.name as string) ?? `Sumber ${i + 1}`}
                  </span>
                  {sim !== null && (
                    <span className="ml-2 text-xs text-neutral-400">
                      {Math.round(sim <= 1 ? sim * 100 : sim)}%
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}

      <details className="rounded-xl border border-c surface-2 p-4">
        <summary className="cursor-pointer text-xs font-medium text-neutral-500 dark:text-neutral-400">
          Data mentah (JSON)
        </summary>
        <pre className="mt-2 max-h-80 overflow-auto rounded-lg surface p-3 text-[11px] leading-relaxed text-neutral-600 dark:text-neutral-400">
          {JSON.stringify(result, null, 2)}
        </pre>
      </details>
    </div>
  );
}
