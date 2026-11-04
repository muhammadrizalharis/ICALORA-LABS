"use client";

import { useState } from "react";
import { apiPost } from "@/lib/api";
import { escapeHtml } from "@/lib/report";
import ReportBar from "@/components/ReportBar";
import TextInput from "@/components/TextInput";

interface Citation {
  doc_id: number;
  source: string;
  title: string | null;
  pub_year: number | null;
  doi: string | null;
  url: string | null;
  relevance: number;
  apa: string;
  bibtex: string;
}
interface CitationResult {
  query: string;
  count: number;
  citations: Citation[];
  corpus_size?: number;
}

export default function CitationTool() {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [res, setRes] = useState<CitationResult | null>(null);
  const [copied, setCopied] = useState<string | null>(null);

  function copy(key: string, value: string) {
    navigator.clipboard.writeText(value);
    setCopied(key);
    setTimeout(() => setCopied(null), 1500);
  }

  async function run() {
    if (!text.trim()) return;
    setLoading(true);
    setError(null);
    setRes(null);
    try {
      setRes(await apiPost<CitationResult>("/tools/citations", { text, top_k: 15 }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Terjadi kesalahan.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <TextInput
        value={text}
        onChange={setText}
        rows={5}
        placeholder="Tempel klaim/kalimat atau topik untuk mencari sumber sitasi dari korpus…"
      />
      <button
        onClick={run}
        disabled={loading || !text.trim()}
        className="rounded-lg bg-[color:var(--brand)] px-5 py-2 text-sm font-medium text-white disabled:opacity-40"
      >
        {loading ? "Mencari…" : "Cari Sitasi"}
      </button>
      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300">
          {error}
        </div>
      )}
      {res && (
        <div className="space-y-3">
          <p className="text-sm text-neutral-500 dark:text-neutral-400">
            {res.count} sumber relevan ditemukan
            {res.corpus_size
              ? ` dari ${res.corpus_size.toLocaleString("id-ID")} dokumen korpus yang dibandingkan`
              : ""}
            .
          </p>
          <ReportBar
            source={text}
            title="Laporan Pencarian Sitasi"
            filename="laporan-sitasi"
            disclaimer="Daftar sitasi ditarik dari korpus akses-terbuka berdasarkan relevansi semantik; verifikasi setiap sumber sebelum dikutip. ID Laporan & hash bersifat reproducible sehingga laporan dapat diverifikasi."
            buildBody={() =>
              `<p class="muted">${res.count} sumber relevan ditemukan${
                res.corpus_size
                  ? ` dari ${res.corpus_size.toLocaleString("id-ID")} dokumen korpus yang dibandingkan`
                  : ""
              }.</p>` +
              res.citations
                .map(
                  (c) =>
                    `<div style="margin:12px 0"><b>${escapeHtml(
                      c.title ?? "[Judul tidak tersedia]",
                    )}</b> <span class="muted">· relevansi ${c.relevance}%</span><br>` +
                    `<span class="muted">${escapeHtml(c.source)} · ${
                      c.pub_year ?? "n.d."
                    }${c.doi ? ` · ${escapeHtml(c.doi)}` : ""}</span><br>` +
                    `<span>${escapeHtml(c.apa)}</span></div>`,
                )
                .join("")
            }
          />
          {res.citations.map((c) => (
            <div key={c.doc_id} className="rounded-xl border border-c surface-2 p-4">
              <div className="flex items-start justify-between gap-3">
                <h3 className="text-sm font-medium text-neutral-900 dark:text-neutral-100">
                  {c.title ?? "[Judul tidak tersedia]"}
                </h3>
                <span className="shrink-0 text-xs font-semibold text-[color:var(--brand)]">
                  {c.relevance}%
                </span>
              </div>
              <div className="mt-1 text-xs text-neutral-400">
                {c.source} · {c.pub_year ?? "n.d."}
                {c.doi && (
                  <>
                    {" · "}
                    <a href={c.url ?? "#"} target="_blank" rel="noopener noreferrer" className="underline">
                      {c.doi}
                    </a>
                  </>
                )}
              </div>
              <p className="mt-2 text-xs text-neutral-600 dark:text-neutral-400">{c.apa}</p>
              <div className="mt-2 flex gap-3">
                <button onClick={() => copy(`apa-${c.doc_id}`, c.apa)} className="text-xs text-[color:var(--brand)] hover:underline">
                  {copied === `apa-${c.doc_id}` ? "Tersalin!" : "Salin APA"}
                </button>
                <button onClick={() => copy(`bib-${c.doc_id}`, c.bibtex)} className="text-xs text-[color:var(--brand)] hover:underline">
                  {copied === `bib-${c.doc_id}` ? "Tersalin!" : "Salin BibTeX"}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
