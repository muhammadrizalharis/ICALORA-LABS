"use client";

import { useState } from "react";
import { apiPost } from "@/lib/api";
import TextInput from "@/components/TextInput";

interface Match {
  title: string | null;
  doi: string | null;
  pub_year: number | null;
  source: string;
  fields: string[];
  relevance: number;
  snippet: string;
}
interface Readiness {
  readiness_score: number | null;
  strengths?: string[];
  gaps?: string[];
  recommended_fields?: string[];
  advice?: string;
}
interface PublikasiResult {
  matches: Match[];
  fields: { field: string; count: number }[];
  sources: { source: string; label: string; count: number }[];
  readiness: Readiness;
  note: string;
}

export default function PublikasiTool() {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [res, setRes] = useState<PublikasiResult | null>(null);

  async function run() {
    if (!text.trim()) return;
    setLoading(true);
    setError(null);
    setRes(null);
    try {
      setRes(await apiPost<PublikasiResult>("/tools/publikasi", { text, top_k: 10 }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Terjadi kesalahan.");
    } finally {
      setLoading(false);
    }
  }

  const r = res?.readiness;

  return (
    <div className="space-y-4">
      <TextInput
        value={text}
        onChange={setText}
        rows={7}
        placeholder="Tempel abstrak/naskah (atau unggah) untuk rekomendasi publikasi & kesiapan…"
      />
      <button
        onClick={run}
        disabled={loading || !text.trim()}
        className="rounded-lg bg-[color:var(--brand)] px-5 py-2 text-sm font-medium text-white disabled:opacity-40"
      >
        {loading ? "Menganalisis…" : "Rekomendasi Publikasi"}
      </button>
      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300">
          {error}
        </div>
      )}
      {res && (
        <div className="space-y-3">
          {r && (
            <div className="rounded-xl border border-c surface-2 p-4">
              <div className="flex items-center justify-between">
                <span className="text-sm text-neutral-500 dark:text-neutral-400">Skor kesiapan</span>
                <span className="text-xl font-bold text-[color:var(--brand)]">
                  {r.readiness_score ?? "—"}
                  {r.readiness_score != null && <span className="text-sm">/100</span>}
                </span>
              </div>
              {r.advice && <p className="mt-2 text-sm text-neutral-700 dark:text-neutral-300">{r.advice}</p>}
              {r.gaps && r.gaps.length > 0 && (
                <ul className="mt-2 list-disc pl-5 text-xs text-neutral-500 dark:text-neutral-400">
                  {r.gaps.map((g, i) => (
                    <li key={i}>{g}</li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {res.fields.length > 0 && (
            <div className="rounded-xl border border-c surface-2 p-4">
              <h3 className="mb-2 text-sm font-medium">Bidang dominan</h3>
              <div className="flex flex-wrap gap-2 text-xs">
                {res.fields.map((f) => (
                  <span key={f.field} className="rounded-full border border-c px-2 py-1">
                    {f.field} · {f.count}
                  </span>
                ))}
              </div>
            </div>
          )}

          <div className="space-y-2">
            <h3 className="text-sm font-medium">Paper terbit paling relevan (acuan jurnal tujuan)</h3>
            {res.matches.map((m, i) => (
              <div key={i} className="rounded-xl border border-c surface-2 p-3">
                <div className="flex items-start justify-between gap-2">
                  <span className="text-sm font-medium text-neutral-900 dark:text-neutral-100">
                    {m.title ?? "[Judul tidak tersedia]"}
                  </span>
                  <span className="shrink-0 text-xs font-semibold text-[color:var(--brand)]">
                    {m.relevance}%
                  </span>
                </div>
                <div className="mt-1 text-xs text-neutral-400">
                  {m.pub_year ?? "?"} · {m.source}
                  {m.doi && (
                    <>
                      {" · "}
                      <a
                        href={`https://doi.org/${m.doi}`}
                        target="_blank"
                        rel="noreferrer"
                        className="underline hover:text-[color:var(--brand)]"
                      >
                        {m.doi}
                      </a>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
          <p className="text-xs text-neutral-400">{res.note}</p>
        </div>
      )}
    </div>
  );
}
