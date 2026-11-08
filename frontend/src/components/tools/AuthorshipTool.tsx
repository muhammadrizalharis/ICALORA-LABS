"use client";

import { useState } from "react";
import { apiPost } from "@/lib/api";
import { escapeHtml } from "@/lib/report";
import ReportBar from "@/components/ReportBar";
import TextInput from "@/components/TextInput";

interface Profile {
  word_count: number;
  sentence_count: number;
  avg_sentence_length: number;
  sentence_length_std: number;
  avg_word_length: number;
  type_token_ratio: number;
  hapax_ratio: number;
  readability_flesch: number;
  punctuation: Record<string, number>;
  top_function_words: Record<string, number>;
}
interface AuthorshipResult {
  profile: Profile;
  comparison?: {
    profile_b: Profile;
    style_similarity: number;
    function_word_similarity?: number;
    structural_similarity?: number;
    confidence?: string;
    verdict: string;
    note?: string;
  };
}

function ProfileCard({ title, p }: { title: string; p: Profile }) {
  return (
    <div className="rounded-xl border border-c surface-2 p-4">
      <div className="mb-3 text-xs font-medium uppercase tracking-wide text-neutral-400">{title}</div>
      <div className="grid grid-cols-2 gap-3 text-sm">
        {[
          ["Kata", p.word_count],
          ["Kalimat", p.sentence_count],
          ["Rata² panjang kalimat", p.avg_sentence_length],
          ["Variasi kalimat (std)", p.sentence_length_std],
          ["Rata² panjang kata", p.avg_word_length],
          ["Keragaman kosakata", p.type_token_ratio],
          ["Hapax ratio", p.hapax_ratio],
          ["Keterbacaan (Flesch)", p.readability_flesch],
        ].map(([l, v]) => (
          <div key={l as string} className="flex justify-between border-b border-c pb-1">
            <span className="text-neutral-500 dark:text-neutral-400">{l}</span>
            <span className="font-medium">{v}</span>
          </div>
        ))}
      </div>
      {Object.keys(p.top_function_words ?? {}).length > 0 && (
        <div className="mt-3">
          <div className="mb-1 text-xs text-neutral-400">Kata fungsi teratas (%)</div>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(p.top_function_words).map(([w, f]) => (
              <span key={w} className="rounded-full border border-c surface px-2 py-0.5 text-xs">
                {w} · {f}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function profileRowsHtml(p: Profile): string {
  const rows: [string, number][] = [
    ["Kata", p.word_count],
    ["Kalimat", p.sentence_count],
    ["Rata² panjang kalimat", p.avg_sentence_length],
    ["Variasi kalimat (std)", p.sentence_length_std],
    ["Rata² panjang kata", p.avg_word_length],
    ["Keragaman kosakata", p.type_token_ratio],
    ["Hapax ratio", p.hapax_ratio],
    ["Keterbacaan (Flesch)", p.readability_flesch],
  ];
  return `<table><tbody>${rows
    .map(([l, v]) => `<tr><td>${escapeHtml(l)}</td><td class="r">${v}</td></tr>`)
    .join("")}</tbody></table>`;
}

export default function AuthorshipTool() {
  const [text, setText] = useState("");
  const [compare, setCompare] = useState("");
  const [showCompare, setShowCompare] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [res, setRes] = useState<AuthorshipResult | null>(null);

  async function run() {
    if (!text.trim()) return;
    setLoading(true);
    setError(null);
    setRes(null);
    try {
      setRes(
        await apiPost<AuthorshipResult>("/tools/authorship", {
          text,
          compare: showCompare && compare.trim() ? compare : null,
        }),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Terjadi kesalahan.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <TextInput value={text} onChange={setText} rows={7} placeholder="Tempel teks untuk dianalisis gaya penulisannya…" />
      <label className="flex items-center gap-2 text-sm text-neutral-600 dark:text-neutral-400">
        <input type="checkbox" checked={showCompare} onChange={(e) => setShowCompare(e.target.checked)} />
        Bandingkan dengan teks kedua (cek kemungkinan penulis sama)
      </label>
      {showCompare && (
        <TextInput value={compare} onChange={setCompare} rows={6} placeholder="Tempel teks pembanding…" />
      )}
      <button
        onClick={run}
        disabled={loading || !text.trim()}
        className="rounded-lg bg-[color:var(--brand)] px-5 py-2 text-sm font-medium text-white disabled:opacity-40"
      >
        {loading ? "Menganalisis…" : "Analisis Gaya"}
      </button>
      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300">
          {error}
        </div>
      )}
      {res && (
        <div className="space-y-4">
          {res.comparison && (
            <div className="flex items-start gap-4 rounded-xl border border-c surface-2 p-5">
              <div className="text-3xl font-bold text-[color:var(--brand)]">
                {res.comparison.style_similarity}%
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-semibold">Kemiripan gaya</span>
                  {res.comparison.confidence && (
                    <span className="rounded-full border border-c px-2 py-0.5 text-[11px] text-neutral-500 dark:text-neutral-400">
                      kepercayaan: {res.comparison.confidence}
                    </span>
                  )}
                </div>
                <p className="text-sm text-neutral-500 dark:text-neutral-400">{res.comparison.verdict}</p>
                {(res.comparison.function_word_similarity != null ||
                  res.comparison.structural_similarity != null) && (
                  <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-neutral-400">
                    <span>kata fungsi: {res.comparison.function_word_similarity}%</span>
                    <span>struktural: {res.comparison.structural_similarity}%</span>
                  </div>
                )}
                {res.comparison.note && (
                  <p className="mt-1 text-[11px] text-neutral-400">{res.comparison.note}</p>
                )}
              </div>
            </div>
          )}
          <div className="grid gap-4 lg:grid-cols-2">
            <ProfileCard title={res.comparison ? "Teks A" : "Profil Gaya"} p={res.profile} />
            {res.comparison && <ProfileCard title="Teks B" p={res.comparison.profile_b} />}
          </div>
          <ReportBar
            source={text + (res.comparison ? "\u0001" + compare : "")}
            title="Laporan Analisis Gaya Penulisan (Authorship)"
            filename="laporan-authorship"
            disclaimer="Analisis stilometri menyajikan profil kuantitatif gaya penulisan sebagai bahan tinjauan; kesamaan gaya bukan bukti tunggal identitas penulis. ID Laporan & hash bersifat reproducible sehingga laporan dapat diverifikasi."
            buildBody={() =>
              (res.comparison
                ? `<p>Kemiripan gaya: <b>${res.comparison.style_similarity}%</b> — ${escapeHtml(
                    res.comparison.verdict,
                  )}</p>`
                : "") +
              `<h2>${res.comparison ? "Teks A" : "Profil Gaya"}</h2>${profileRowsHtml(res.profile)}` +
              (res.comparison
                ? `<h2>Teks B</h2>${profileRowsHtml(res.comparison.profile_b)}`
                : "")
            }
          />
        </div>
      )}
    </div>
  );
}
