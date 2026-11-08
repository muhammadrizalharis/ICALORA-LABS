"use client";

import { useState } from "react";
import { apiPost } from "@/lib/api";
import { escapeHtml } from "@/lib/report";
import ReportBar from "@/components/ReportBar";
import TextInput from "@/components/TextInput";

interface TocEntry {
  level: number;
  title: string;
  number: string;
}
interface TocResult {
  entries: TocEntry[];
  markdown: string;
}

export default function TocTool() {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [res, setRes] = useState<TocResult | null>(null);
  const [copied, setCopied] = useState(false);

  async function run() {
    if (!text.trim()) return;
    setLoading(true);
    setError(null);
    setRes(null);
    try {
      setRes(await apiPost<TocResult>("/tools/toc", { text }));
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
        rows={8}
        placeholder="Tempel isi dokumen (atau unggah PDF/DOCX) untuk membuat daftar isi…"
      />
      <button
        onClick={run}
        disabled={loading || !text.trim()}
        className="w-full rounded-xl bg-[color:var(--brand)] px-5 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-40"
      >
        {loading ? "Menyusun…" : "Buat Daftar Isi"}
      </button>
      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300">
          {error}
        </div>
      )}
      {res && (
        <div className="space-y-3">
          <div className="rounded-xl border border-c surface-2 p-4">
            {res.entries.map((e, i) => (
              <div
                key={i}
                className="py-0.5 text-sm text-neutral-800 dark:text-neutral-200"
                style={{ paddingLeft: `${(e.level - 1) * 1.25}rem` }}
              >
                <span className="mr-2 text-neutral-400">{e.number}</span>
                {e.title}
              </div>
            ))}
          </div>
          <button
            onClick={() => {
              navigator.clipboard.writeText(res.markdown);
              setCopied(true);
              setTimeout(() => setCopied(false), 1500);
            }}
            className="rounded-lg border border-c px-4 py-1.5 text-xs text-neutral-600 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-900"
          >
            {copied ? "Tersalin ✓" : "Salin Markdown"}
          </button>
          <ReportBar
            source={text}
            title="Laporan Daftar Isi"
            filename="laporan-daftar-isi"
            disclaimer="Daftar isi disusun otomatis dari struktur dokumen dan sebaiknya diperiksa kembali. ID Laporan & hash bersifat reproducible sehingga laporan dapat diverifikasi."
            buildBody={() =>
              `<h2>Daftar Isi</h2><table><tbody>${res.entries
                .map(
                  (e) =>
                    `<tr><td style="width:70px" class="muted">${escapeHtml(
                      e.number,
                    )}</td><td style="padding-left:${(e.level - 1) * 18}px">${escapeHtml(
                      e.title,
                    )}</td></tr>`,
                )
                .join("")}</tbody></table>`
            }
          />
        </div>
      )}
    </div>
  );
}
