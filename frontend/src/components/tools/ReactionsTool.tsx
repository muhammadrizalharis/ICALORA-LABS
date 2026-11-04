"use client";

import { useState } from "react";
import { apiPost } from "@/lib/api";
import { escapeHtml } from "@/lib/report";
import ReportBar from "@/components/ReportBar";
import TextInput from "@/components/TextInput";

interface Reaction {
  persona: string;
  reaction: string;
  sentiment: string;
}
interface ReactionsResult {
  reactions: Reaction[];
  overall_sentiment: string | null;
  clarity_score: number | null;
  engagement_score: number | null;
  summary: string;
}

function sentimentColor(s: string): string {
  const v = s?.toLowerCase() ?? "";
  if (v.includes("positif")) return "#22c55e";
  if (v.includes("negatif")) return "#ef4444";
  return "#eab308";
}

export default function ReactionsTool() {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [res, setRes] = useState<ReactionsResult | null>(null);

  async function run() {
    if (!text.trim()) return;
    setLoading(true);
    setError(null);
    setRes(null);
    try {
      setRes(await apiPost<ReactionsResult>("/tools/reader-reactions", { text }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Terjadi kesalahan.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <TextInput value={text} onChange={setText} rows={8} placeholder="Tempel teks untuk diprediksi reaksi pembacanya…" />
      <button
        onClick={run}
        disabled={loading || !text.trim()}
        className="rounded-lg bg-[color:var(--brand)] px-5 py-2 text-sm font-medium text-white disabled:opacity-40"
      >
        {loading ? "Menganalisis…" : "Prediksi Reaksi"}
      </button>
      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300">
          {error}
        </div>
      )}
      {res && (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-3">
            {[
              ["Sentimen", res.overall_sentiment ?? "—"],
              ["Kejelasan", res.clarity_score !== null ? `${res.clarity_score}` : "—"],
              ["Keterlibatan", res.engagement_score !== null ? `${res.engagement_score}` : "—"],
            ].map(([l, v]) => (
              <div key={l as string} className="rounded-xl border border-c surface-2 p-4 text-center">
                <div className="text-lg font-semibold">{v}</div>
                <div className="text-xs text-neutral-500 dark:text-neutral-400">{l}</div>
              </div>
            ))}
          </div>
          {res.summary && <p className="text-sm text-neutral-500 dark:text-neutral-400">{res.summary}</p>}
          <div className="space-y-2">
            {res.reactions?.map((r, i) => (
              <div key={i} className="flex items-start gap-3 rounded-xl border border-c surface-2 p-4">
                <span
                  className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ background: sentimentColor(r.sentiment) }}
                />
                <div>
                  <div className="text-sm font-medium">{r.persona}</div>
                  <p className="text-sm text-neutral-600 dark:text-neutral-400">{r.reaction}</p>
                </div>
              </div>
            ))}
          </div>
          <ReportBar
            source={text}
            title="Laporan Prediksi Reaksi Pembaca"
            filename="laporan-reaksi-pembaca"
            disclaimer="Prediksi reaksi dihasilkan model bahasa sebagai simulasi persona pembaca untuk bahan evaluasi tulisan. ID Laporan & hash bersifat reproducible sehingga laporan dapat diverifikasi."
            buildBody={() =>
              `<p>Sentimen keseluruhan: <b>${escapeHtml(
                res.overall_sentiment ?? "—",
              )}</b> · Kejelasan: <b>${res.clarity_score ?? "—"}</b> · Keterlibatan: <b>${
                res.engagement_score ?? "—"
              }</b></p>` +
              (res.summary ? `<p class="muted">${escapeHtml(res.summary)}</p>` : "") +
              `<h2>Reaksi per Persona</h2>${res.reactions
                .map(
                  (r) =>
                    `<div style="margin:10px 0"><b>${escapeHtml(r.persona)}</b> <span class="muted">(${escapeHtml(
                      r.sentiment,
                    )})</span><br>${escapeHtml(r.reaction)}</div>`,
                )
                .join("")}`
            }
          />
        </div>
      )}
    </div>
  );
}
