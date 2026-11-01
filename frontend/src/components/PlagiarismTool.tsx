"use client";

import { useState } from "react";
import { apiPost } from "@/lib/api";
import TextInput from "@/components/TextInput";

interface Source {
  doc_id: number;
  source: string;
  external_id: string;
  doi: string | null;
  title: string | null;
  pub_year: number | null;
  semantic_similarity: number;
  lexical_similarity: number;
  similarity: number;
  snippet: string;
}

interface Report {
  overall_similarity: number;
  paraphrase_similarity: number;
  word_count: number;
  char_count: number;
  sources: Source[];
}

function ScoreRing({ value, label, tone }: { value: number; label: string; tone: string }) {
  return (
    <div className="flex flex-col items-center">
      <div
        className={`flex h-24 w-24 items-center justify-center rounded-full border-4 text-2xl font-bold ${tone}`}
      >
        {value.toFixed(0)}%
      </div>
      <div className="mt-2 text-center text-xs font-medium text-neutral-500 dark:text-neutral-400">{label}</div>
    </div>
  );
}

function toneForScore(v: number): string {
  if (v >= 40) return "border-red-400 text-red-600";
  if (v >= 15) return "border-amber-400 text-amber-600";
  return "border-emerald-400 text-emerald-600";
}

export default function PlagiarismTool() {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<Report | null>(null);

  async function run() {
    setLoading(true);
    setError(null);
    setReport(null);
    try {
      const res = await apiPost<Report>("/tools/plagiarism", { text, top_k: 10 });
      setReport(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Terjadi kesalahan");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      <TextInput
        value={text}
        onChange={setText}
        placeholder="Tempel teks/abstrak yang ingin diperiksa keasliannya…"
        rows={10}
      />
      <div className="flex items-center gap-3">
        <button
          onClick={run}
          disabled={loading || text.trim().length === 0}
          className="rounded-lg bg-neutral-900 px-5 py-2 text-sm font-medium text-white disabled:opacity-40 dark:bg-neutral-100 dark:text-neutral-900"
        >
          {loading ? "Memeriksa…" : "Periksa Kemiripan"}
        </button>
        <span className="text-xs text-neutral-400 dark:text-neutral-500">
          Dibandingkan dengan korpus akses-terbuka ICALORA-LABS.
        </span>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
          {error}
        </div>
      )}

      {report && (
        <div className="space-y-5 rounded-xl border border-c p-5">
          <div className="flex flex-wrap items-center gap-8">
            <ScoreRing
              value={report.overall_similarity}
              label="Indeks Kemiripan (salinan)"
              tone={toneForScore(report.overall_similarity)}
            />
            <ScoreRing
              value={report.paraphrase_similarity}
              label="Risiko Parafrase (semantik)"
              tone={toneForScore(report.paraphrase_similarity)}
            />
            <div className="text-sm text-neutral-500 dark:text-neutral-400">
              <div>{report.word_count} kata · {report.char_count} karakter</div>
              <div>{report.sources.length} sumber teratas ditemukan</div>
            </div>
          </div>

          <div>
            <div className="mb-2 text-sm font-semibold text-neutral-800 dark:text-neutral-200">Sumber Teratas</div>
            <ul className="space-y-3">
              {report.sources.map((s) => (
                <li key={s.doc_id} className="rounded-lg border border-c p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium text-neutral-900 dark:text-neutral-100">
                        {s.title || "(tanpa judul)"}
                      </div>
                      <div className="mt-0.5 text-xs text-neutral-400 dark:text-neutral-500">
                        {s.source}
                        {s.pub_year ? ` · ${s.pub_year}` : ""}
                        {s.doi ? (
                          <>
                            {" · "}
                            <a
                              href={`https://doi.org/${s.doi}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="underline"
                            >
                              {s.doi}
                            </a>
                          </>
                        ) : null}
                      </div>
                    </div>
                    <div className="shrink-0 text-right text-xs">
                      <div className={`font-bold ${toneForScore(s.similarity).split(" ")[1]}`}>
                        {s.similarity.toFixed(0)}%
                      </div>
                      <div className="text-neutral-400 dark:text-neutral-500">
                        sal {s.lexical_similarity.toFixed(0)} · sem {s.semantic_similarity.toFixed(0)}
                      </div>
                    </div>
                  </div>
                  {s.snippet && (
                    <p className="mt-2 line-clamp-3 text-xs text-neutral-500 dark:text-neutral-400">{s.snippet}</p>
                  )}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
