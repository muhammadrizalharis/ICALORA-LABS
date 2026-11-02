"use client";

import { useState } from "react";
import { apiPost } from "@/lib/api";
import TextInput from "@/components/TextInput";

interface Finding {
  category: string;
  char: string;
  codepoint: string;
  position: number;
}
interface Typo {
  wrong: string;
  suggestion: string;
}
interface HiddenResult {
  risk: string;
  total_hidden: number;
  counts: Record<string, number>;
  findings: Finding[];
  typos: Typo[];
  cleaned_text: string;
  note: string;
}

const RISK_COLOR: Record<string, string> = {
  bersih: "text-emerald-600 dark:text-emerald-400",
  sedang: "text-amber-600 dark:text-amber-400",
  tinggi: "text-rose-600 dark:text-rose-400",
};

export default function HiddenTextTool() {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [res, setRes] = useState<HiddenResult | null>(null);
  const [copied, setCopied] = useState(false);

  async function run() {
    if (!text.trim()) return;
    setLoading(true);
    setError(null);
    setRes(null);
    try {
      setRes(await apiPost<HiddenResult>("/tools/hidden-text", { text, check_typos: true }));
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
        placeholder="Tempel teks (atau unggah dokumen) untuk memindai teks tersembunyi & typo…"
      />
      <button
        onClick={run}
        disabled={loading || !text.trim()}
        className="rounded-lg bg-[color:var(--brand)] px-5 py-2 text-sm font-medium text-white disabled:opacity-40"
      >
        {loading ? "Memindai…" : "Pindai"}
      </button>
      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300">
          {error}
        </div>
      )}
      {res && (
        <div className="space-y-3">
          <div className="rounded-xl border border-c surface-2 p-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-neutral-500 dark:text-neutral-400">Tingkat risiko</span>
              <span className={`text-lg font-bold capitalize ${RISK_COLOR[res.risk] ?? ""}`}>
                {res.risk}
              </span>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-5">
              {Object.entries(res.counts).map(([k, v]) => (
                <div key={k} className="rounded-lg border border-c surface p-2 text-center">
                  <div className="text-lg font-semibold">{v}</div>
                  <div className="text-[10px] text-neutral-400">{k}</div>
                </div>
              ))}
            </div>
          </div>

          {res.findings.length > 0 && (
            <div className="rounded-xl border border-c surface-2 p-4">
              <h3 className="mb-2 text-sm font-medium">Karakter tersembunyi ({res.total_hidden})</h3>
              <div className="max-h-48 space-y-1 overflow-auto text-xs">
                {res.findings.map((f, i) => (
                  <div key={i} className="flex justify-between gap-2 text-neutral-600 dark:text-neutral-300">
                    <span>{f.char}</span>
                    <span className="text-neutral-400">
                      {f.codepoint} @ {f.position}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {res.typos.length > 0 && (
            <div className="rounded-xl border border-c surface-2 p-4">
              <h3 className="mb-2 text-sm font-medium">Dugaan typo ({res.typos.length})</h3>
              <div className="flex flex-wrap gap-2 text-xs">
                {res.typos.map((t, i) => (
                  <span key={i} className="rounded-full border border-c px-2 py-1">
                    <span className="text-rose-500 line-through">{t.wrong}</span> →{" "}
                    <span className="text-emerald-500">{t.suggestion}</span>
                  </span>
                ))}
              </div>
            </div>
          )}

          <button
            onClick={() => {
              navigator.clipboard.writeText(res.cleaned_text);
              setCopied(true);
              setTimeout(() => setCopied(false), 1500);
            }}
            className="rounded-lg border border-c px-4 py-1.5 text-xs text-neutral-600 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-900"
          >
            {copied ? "Tersalin ✓" : "Salin Teks Bersih"}
          </button>
          <p className="text-xs text-neutral-400">{res.note}</p>
        </div>
      )}
    </div>
  );
}
