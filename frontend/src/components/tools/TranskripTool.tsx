"use client";

import { useRef, useState } from "react";
import { API_BASE } from "@/lib/api";
import { escapeHtml } from "@/lib/report";
import ReportBar from "@/components/ReportBar";

interface Segment {
  start: number;
  end: number;
  text: string;
}
interface TranscribeResult {
  text: string;
  language: string;
  language_probability: number;
  duration: number;
  segments: Segment[];
  model: string;
}

const ACCEPT = ".mp3,.wav,.m4a,.ogg,.flac,.aac,.opus,.mp4,.webm,.mkv,.mov,.wma";

function fmt(t: number): string {
  const m = Math.floor(t / 60);
  const s = Math.floor(t % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function TranskripTool() {
  const [fileName, setFileName] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [res, setRes] = useState<TranscribeResult | null>(null);
  const [copied, setCopied] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  async function handleFile(file: File) {
    setError(null);
    setRes(null);
    setFileName(file.name);
    setLoading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const r = await fetch(`${API_BASE}/tools/transcribe`, {
        method: "POST",
        body: form,
        cache: "no-store",
      });
      if (!r.ok) {
        let detail = `${r.status}`;
        try {
          const err = await r.json();
          if (err?.detail) detail = err.detail;
        } catch {
          /* abaikan */
        }
        throw new Error(detail);
      }
      setRes((await r.json()) as TranscribeResult);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Terjadi kesalahan.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <div
        onClick={() => !loading && fileRef.current?.click()}
        className="cursor-pointer rounded-xl border border-dashed border-c surface-2 p-6 text-center transition hover:border-[color:var(--brand)]"
      >
        <input
          ref={fileRef}
          type="file"
          accept={ACCEPT}
          className="hidden"
          onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
        />
        {loading ? (
          <span className="text-sm text-neutral-400">
            Mentranskripsi {fileName}… (bisa beberapa menit untuk audio panjang)
          </span>
        ) : fileName && res ? (
          <span className="text-sm text-emerald-600 dark:text-emerald-400">🎧 {fileName}</span>
        ) : (
          <span className="text-sm text-neutral-500 dark:text-neutral-400">
            Klik untuk unggah audio/video (mp3, wav, m4a, mp4, …) — maks 50 MB.
          </span>
        )}
      </div>

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300">
          {error}
        </div>
      )}

      {res && (
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2 text-xs text-neutral-400">
            <span className="rounded-full border border-c px-2 py-1">
              Bahasa: {res.language} ({Math.round(res.language_probability * 100)}%)
            </span>
            <span className="rounded-full border border-c px-2 py-1">Durasi: {fmt(res.duration)}</span>
            <span className="rounded-full border border-c px-2 py-1">Model: {res.model}</span>
          </div>

          <div className="whitespace-pre-wrap rounded-xl border border-c surface-2 p-4 text-sm text-neutral-800 dark:text-neutral-200">
            {res.text || "(Tidak ada ucapan terdeteksi.)"}
          </div>

          {res.segments.length > 0 && (
            <div className="rounded-xl border border-c surface-2 p-4">
              <h3 className="mb-2 text-sm font-medium">Segmen berwaktu</h3>
              <div className="max-h-64 space-y-1 overflow-auto text-xs">
                {res.segments.map((s, i) => (
                  <div key={i} className="flex gap-3">
                    <span className="shrink-0 font-mono text-neutral-400">
                      {fmt(s.start)}–{fmt(s.end)}
                    </span>
                    <span className="text-neutral-700 dark:text-neutral-300">{s.text}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {res.text && (
            <button
              onClick={() => {
                navigator.clipboard.writeText(res.text);
                setCopied(true);
                setTimeout(() => setCopied(false), 1500);
              }}
              className="rounded-lg border border-c px-4 py-1.5 text-xs text-neutral-600 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-900"
            >
              {copied ? "Tersalin ✓" : "Salin Transkrip"}
            </button>
          )}
          <ReportBar
            source={(fileName ?? "") + "\n" + res.text}
            title="Laporan Transkrip Audio"
            filename="laporan-transkrip"
            disclaimer="Transkrip dihasilkan otomatis oleh model pengenalan suara dan dapat memuat kesalahan; tinjau kembali untuk keperluan resmi. ID Laporan & hash bersifat reproducible sehingga laporan dapat diverifikasi."
            buildBody={() =>
              `<p class="muted">${fileName ? `Berkas: ${escapeHtml(fileName)} · ` : ""}Bahasa: ${escapeHtml(
                res.language,
              )} (${Math.round(res.language_probability * 100)}%) · Durasi: ${fmt(
                res.duration,
              )} · Model: ${escapeHtml(res.model)}</p>` +
              `<h2>Transkrip</h2><div class="doc">${escapeHtml(
                res.text || "(Tidak ada ucapan terdeteksi.)",
              )}</div>` +
              (res.segments.length
                ? `<h2>Segmen Berwaktu</h2><table><tbody>${res.segments
                    .map(
                      (s) =>
                        `<tr><td class="mono" style="width:110px">${fmt(s.start)}–${fmt(
                          s.end,
                        )}</td><td>${escapeHtml(s.text)}</td></tr>`,
                    )
                    .join("")}</tbody></table>`
                : "")
            }
          />
        </div>
      )}
    </div>
  );
}
