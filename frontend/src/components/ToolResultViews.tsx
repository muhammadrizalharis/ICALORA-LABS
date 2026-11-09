"use client";

import { useState } from "react";

/* ─────────────────────────── shared primitives ─────────────────────────── */

function toneFor(pct: number): string {
  return pct >= 70 ? "#ef4444" : pct >= 45 ? "#f59e0b" : "var(--brand)";
}

function fmtPct(v: number): string {
  if (v > 0 && v < 1) return "<1";
  if (v < 10) return v.toFixed(1).replace(/\.0$/, "");
  return Math.round(v).toString();
}

export function Gauge({
  value,
  label,
  tone,
}: {
  value: number;
  label: string;
  tone?: string;
}) {
  const pct = Math.max(0, Math.min(100, value));
  const col = tone ?? toneFor(pct);
  return (
    <div className="flex flex-col items-center">
      <div
        className="grid h-28 w-28 place-items-center rounded-full"
        style={{ background: `conic-gradient(${col} ${pct * 3.6}deg, var(--brand-soft) 0deg)` }}
      >
        <div className="grid h-20 w-20 place-items-center rounded-full surface">
          <span className="text-xl font-bold" style={{ color: col }}>
            {fmtPct(pct)}%
          </span>
        </div>
      </div>
      <span className="mt-2 text-center text-xs text-neutral-500 dark:text-neutral-400">
        {label}
      </span>
    </div>
  );
}

function Bar({ label, value, max = 100 }: { label: string; value: number; max?: number }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="text-neutral-600 dark:text-neutral-300">{label}</span>
        <span className="font-semibold text-neutral-800 dark:text-neutral-100">
          {Number.isInteger(value) ? value : value.toFixed(1)}
          {max === 100 ? "%" : ""}
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full surface">
        <div
          className="h-full rounded-full"
          style={{ width: `${pct}%`, background: toneFor(pct) }}
        />
      </div>
    </div>
  );
}

function Section({
  title,
  children,
  right,
}: {
  title: string;
  children: React.ReactNode;
  right?: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-c surface-2 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-neutral-700 dark:text-neutral-200">{title}</h3>
        {right}
      </div>
      {children}
    </div>
  );
}

function Pill({ children, tone }: { children: React.ReactNode; tone?: string }) {
  return (
    <span
      className="rounded-full px-3 py-1 text-xs font-semibold"
      style={{
        background: `color-mix(in srgb, ${tone ?? "var(--brand)"} 15%, transparent)`,
        color: tone ?? "var(--brand)",
      }}
    >
      {children}
    </span>
  );
}

function CopyButton({ text, label = "Salin" }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => {
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
      className="text-xs font-medium text-[color:var(--brand)] hover:underline"
    >
      {copied ? "Tersalin!" : label}
    </button>
  );
}

function num(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

/* ───────────────────────────── AI Detector ─────────────────────────────── */

function AiDetectorView({ result }: { result: Record<string, unknown> }) {
  const prob = num(result.ai_probability);
  const verdict = (result.verdict as string) ?? "";
  const flagged = Array.isArray(result.flagged_sentences)
    ? (result.flagged_sentences as string[])
    : [];
  const signals = (result.signals as Record<string, number>) ?? {};
  const components: [string, unknown][] = [
    ["Statistik", result.stat_probability],
    ["Model Bahasa", result.llm_probability],
    ["Model Terlatih", result.model_probability],
    ["Model Embedding", result.emb_model_probability],
  ];
  const tone = prob === null ? "var(--brand)" : toneFor(prob);
  const signalLabels: Record<string, string> = {
    burstiness: "Burstiness (variasi ritme)",
    type_token_ratio: "Rasio tipe-token",
    avg_sentence_length: "Rata-rata panjang kalimat",
    bigram_repetition: "Pengulangan bigram",
    cliche_density: "Kepadatan klise",
    personal_ratio: "Rasio kata personal",
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-6 rounded-xl border border-c surface-2 p-5">
        {prob !== null ? (
          <Gauge value={prob} label="Probabilitas AI" />
        ) : (
          <div className="text-sm text-neutral-500">Tidak cukup teks untuk analisis.</div>
        )}
        <div className="min-w-0 flex-1 space-y-3">
          {verdict && <Pill tone={tone}>{verdict}</Pill>}
          <div className="grid gap-2 sm:grid-cols-2">
            {components
              .filter(([, v]) => num(v) !== null)
              .map(([label, v]) => (
                <Bar key={label} label={label} value={num(v) as number} />
              ))}
          </div>
        </div>
      </div>

      {Object.keys(signals).length > 0 && (
        <Section title="Sinyal Linguistik">
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {Object.entries(signalLabels)
              .filter(([k]) => num(signals[k]) !== null)
              .map(([k, label]) => (
                <div key={k} className="rounded-lg border border-c surface px-3 py-2">
                  <div className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
                    {signals[k]}
                  </div>
                  <div className="text-[11px] text-neutral-400">{label}</div>
                </div>
              ))}
          </div>
        </Section>
      )}

      {flagged.length > 0 && (
        <Section title={`Kalimat Ditandai Mirip-AI (${flagged.length})`}>
          <ul className="space-y-2">
            {flagged.map((s, i) => (
              <li
                key={i}
                className="rounded-lg border-l-2 border-amber-400 bg-amber-400/5 px-3 py-2 text-sm text-neutral-700 dark:text-neutral-300"
              >
                {s}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {typeof result.note === "string" && (
        <p className="text-xs leading-relaxed text-neutral-400">{result.note}</p>
      )}
    </div>
  );
}

/* ────────────────────────────── AI Grader ──────────────────────────────── */

function AiGraderView({ result }: { result: Record<string, unknown> }) {
  const score = num(result.overall_score);
  const grade = (result.grade as string) ?? null;
  const criteria = Array.isArray(result.criteria)
    ? (result.criteria as Record<string, unknown>[])
    : [];
  const suggestions = Array.isArray(result.suggestions)
    ? (result.suggestions as string[])
    : [];
  const tone = score === null ? "var(--brand)" : toneFor(100 - score);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-6 rounded-xl border border-c surface-2 p-5">
        {score !== null && <Gauge value={score} label="Skor Keseluruhan" tone={tone} />}
        {grade && (
          <div className="flex flex-col items-center">
            <div
              className="grid h-24 w-24 place-items-center rounded-2xl text-4xl font-black"
              style={{ background: "var(--brand-soft)", color: tone }}
            >
              {grade}
            </div>
            <span className="mt-2 text-xs text-neutral-400">Nilai Huruf</span>
          </div>
        )}
        {typeof result.summary === "string" && (
          <p className="min-w-0 flex-1 text-sm leading-relaxed text-neutral-700 dark:text-neutral-300">
            {result.summary}
          </p>
        )}
      </div>

      {criteria.length > 0 && (
        <Section title="Penilaian per Kriteria">
          <div className="space-y-4">
            {criteria.map((c, i) => {
              const cs = num(c.score);
              return (
                <div key={i}>
                  <Bar label={(c.name as string) ?? `Kriteria ${i + 1}`} value={cs ?? 0} />
                  {typeof c.feedback === "string" && c.feedback && (
                    <p className="mt-1 text-xs text-neutral-500 dark:text-neutral-400">
                      {c.feedback}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        </Section>
      )}

      {suggestions.length > 0 && (
        <Section title="Saran Perbaikan">
          <ul className="space-y-2">
            {suggestions.map((s, i) => (
              <li key={i} className="flex gap-2 text-sm text-neutral-700 dark:text-neutral-300">
                <span className="text-[color:var(--brand)]">→</span>
                <span>{s}</span>
              </li>
            ))}
          </ul>
        </Section>
      )}
    </div>
  );
}

/* ─────────────────────────── Citation Finder ───────────────────────────── */

const CITE_STYLES: { key: string; label: string }[] = [
  { key: "apa", label: "APA" },
  { key: "mla", label: "MLA" },
  { key: "ieee", label: "IEEE" },
  { key: "harvard", label: "Harvard" },
  { key: "vancouver", label: "Vancouver" },
  { key: "bibtex", label: "BibTeX" },
  { key: "ris", label: "RIS" },
];

function CitationFinderView({ result }: { result: Record<string, unknown> }) {
  const citations = Array.isArray(result.citations)
    ? (result.citations as Record<string, unknown>[])
    : [];
  const [style, setStyle] = useState("apa");
  const available = CITE_STYLES.filter((s) =>
    citations.some((c) => typeof c[s.key] === "string"),
  );

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-c surface-2 p-4">
        <div className="text-sm text-neutral-600 dark:text-neutral-300">
          <span className="font-semibold text-neutral-900 dark:text-neutral-100">
            {citations.length}
          </span>{" "}
          sumber ditemukan
          {typeof result.query === "string" && result.query && (
            <> untuk “{result.query}”</>
          )}
        </div>
        <div className="flex flex-wrap gap-1">
          {available.map((s) => (
            <button
              key={s.key}
              onClick={() => setStyle(s.key)}
              className={`rounded-lg px-3 py-1 text-xs font-medium transition ${
                style === s.key
                  ? "bg-[color:var(--brand)] text-white"
                  : "surface text-neutral-600 hover:opacity-80 dark:text-neutral-300"
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      <ul className="space-y-3">
        {citations.map((c, i) => {
          const formatted = (c[style] as string) ?? "";
          const rel = num(c.relevance);
          return (
            <li key={i} className="rounded-xl border border-c surface-2 p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold text-neutral-900 dark:text-neutral-100">
                    {(c.title as string) ?? "[Judul tidak tersedia]"}
                  </div>
                  <div className="mt-0.5 flex flex-wrap items-center gap-2 text-[11px] text-neutral-400">
                    {c.source != null && (
                      <span className="uppercase">{c.source as string}</span>
                    )}
                    {c.pub_year != null && <span>{c.pub_year as number}</span>}
                    {typeof c.url === "string" && (
                      <a
                        href={c.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[color:var(--brand)] hover:underline"
                      >
                        DOI
                      </a>
                    )}
                  </div>
                </div>
                {rel !== null && <Pill>{fmtPct(rel)}% relevan</Pill>}
              </div>
              {formatted && (
                <div className="mt-3 rounded-lg surface p-3">
                  <div className="mb-1 flex items-center justify-between">
                    <span className="text-[11px] font-medium uppercase text-neutral-400">
                      {CITE_STYLES.find((s) => s.key === style)?.label}
                    </span>
                    <CopyButton text={formatted} />
                  </div>
                  <pre className="whitespace-pre-wrap break-words font-mono text-xs leading-relaxed text-neutral-700 dark:text-neutral-300">
                    {formatted}
                  </pre>
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/* ───────────────────────────── Authorship ──────────────────────────────── */

const PROFILE_LABELS: Record<string, string> = {
  word_count: "Jumlah kata",
  sentence_count: "Jumlah kalimat",
  avg_sentence_length: "Rata-rata panjang kalimat",
  sentence_length_std: "Simpangan panjang kalimat",
  avg_word_length: "Rata-rata panjang kata",
  type_token_ratio: "Rasio tipe-token",
  hapax_ratio: "Rasio hapax",
  readability_flesch: "Keterbacaan (Flesch)",
};

function ProfileGrid({ profile }: { profile: Record<string, unknown> }) {
  return (
    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
      {Object.entries(PROFILE_LABELS)
        .filter(([k]) => num(profile[k]) !== null)
        .map(([k, label]) => (
          <div key={k} className="rounded-lg border border-c surface px-3 py-2">
            <div className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
              {profile[k] as number}
            </div>
            <div className="text-[11px] text-neutral-400">{label}</div>
          </div>
        ))}
    </div>
  );
}

function AuthorshipView({ result }: { result: Record<string, unknown> }) {
  const profile = (result.profile as Record<string, unknown>) ?? {};
  const comparison = result.comparison as Record<string, unknown> | undefined;
  const sim = comparison ? num(comparison.style_similarity) : null;

  return (
    <div className="space-y-5">
      {comparison && sim !== null && (
        <div className="flex flex-wrap items-center gap-6 rounded-xl border border-c surface-2 p-5">
          <Gauge value={sim} label="Kemiripan Gaya" tone={toneFor(sim)} />
          <div className="min-w-0 flex-1 space-y-3">
            {typeof comparison.verdict === "string" && (
              <Pill tone={toneFor(sim)}>{comparison.verdict}</Pill>
            )}
            <div className="grid gap-2 sm:grid-cols-2">
              {num(comparison.function_word_similarity) !== null && (
                <Bar
                  label="Kemiripan kata fungsi"
                  value={comparison.function_word_similarity as number}
                />
              )}
              {num(comparison.structural_similarity) !== null && (
                <Bar
                  label="Kemiripan struktural"
                  value={comparison.structural_similarity as number}
                />
              )}
            </div>
            {typeof comparison.confidence === "string" && (
              <div className="text-xs text-neutral-400">
                Kepercayaan: {comparison.confidence}
              </div>
            )}
          </div>
        </div>
      )}

      <Section title={comparison ? "Profil Stilometrik — Teks A" : "Profil Stilometrik"}>
        <ProfileGrid profile={profile} />
      </Section>

      {comparison?.profile_b != null && (
        <Section title="Profil Stilometrik — Teks B">
          <ProfileGrid profile={comparison.profile_b as Record<string, unknown>} />
        </Section>
      )}

      {typeof (comparison?.note ?? result.note) === "string" && (
        <p className="text-xs leading-relaxed text-neutral-400">
          {(comparison?.note ?? result.note) as string}
        </p>
      )}
    </div>
  );
}

/* ───────────────────────────── Hidden Text ─────────────────────────────── */

const RISK_TONE: Record<string, string> = {
  bersih: "var(--brand)",
  sedang: "#f59e0b",
  tinggi: "#ef4444",
};

const COUNT_LABELS: Record<string, string> = {
  invisible: "Karakter tak terlihat",
  bidi_control: "Kontrol bidi",
  odd_space: "Spasi tak lazim",
  homoglyph: "Homoglif",
  control: "Karakter kontrol",
};

function HiddenTextView({ result }: { result: Record<string, unknown> }) {
  const risk = (result.risk as string) ?? "bersih";
  const counts = (result.counts as Record<string, number>) ?? {};
  const findings = Array.isArray(result.findings)
    ? (result.findings as Record<string, unknown>[])
    : [];
  const typos = Array.isArray(result.typos) ? (result.typos as Record<string, unknown>[]) : [];
  const total = num(result.total_hidden) ?? findings.length;
  const tone = RISK_TONE[risk] ?? "var(--brand)";

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-4 rounded-xl border border-c surface-2 p-5">
        <Pill tone={tone}>Risiko: {risk}</Pill>
        <div className="text-sm text-neutral-600 dark:text-neutral-300">
          <span className="font-semibold text-neutral-900 dark:text-neutral-100">{total}</span>{" "}
          karakter tersembunyi · {typos.length} typo
        </div>
      </div>

      {Object.values(counts).some((v) => v > 0) && (
        <Section title="Rincian Temuan">
          <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-5">
            {Object.entries(COUNT_LABELS).map(([k, label]) => (
              <div key={k} className="rounded-lg border border-c surface px-3 py-2 text-center">
                <div
                  className="text-lg font-bold"
                  style={{ color: (counts[k] ?? 0) > 0 ? "#ef4444" : "var(--brand)" }}
                >
                  {counts[k] ?? 0}
                </div>
                <div className="text-[11px] text-neutral-400">{label}</div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {findings.length > 0 && (
        <Section title={`Karakter Mencurigakan (${findings.length})`}>
          <div className="max-h-64 overflow-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-neutral-400">
                <tr>
                  <th className="pb-2 pr-3 font-medium">Kategori</th>
                  <th className="pb-2 pr-3 font-medium">Karakter</th>
                  <th className="pb-2 pr-3 font-medium">Kode</th>
                  <th className="pb-2 font-medium">Posisi</th>
                </tr>
              </thead>
              <tbody className="text-neutral-700 dark:text-neutral-300">
                {findings.slice(0, 100).map((f, i) => (
                  <tr key={i} className="border-t border-c">
                    <td className="py-1.5 pr-3">{(f.category as string) ?? "—"}</td>
                    <td className="py-1.5 pr-3">{(f.char as string) ?? "—"}</td>
                    <td className="py-1.5 pr-3 font-mono">{(f.codepoint as string) ?? "—"}</td>
                    <td className="py-1.5">{(f.position as number) ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      )}

      {typos.length > 0 && (
        <Section title={`Dugaan Typo (${typos.length})`}>
          <ul className="space-y-1.5">
            {typos.slice(0, 50).map((t, i) => (
              <li key={i} className="flex items-center gap-2 text-sm">
                <span className="font-mono text-red-500 line-through">
                  {(t.word as string) ?? (t.original as string) ?? ""}
                </span>
                {(t.suggestion as string) && (
                  <>
                    <span className="text-neutral-400">→</span>
                    <span className="font-mono text-emerald-600 dark:text-emerald-400">
                      {t.suggestion as string}
                    </span>
                  </>
                )}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {typeof result.cleaned_text === "string" && total > 0 && (
        <Section
          title="Teks Bersih"
          right={<CopyButton text={result.cleaned_text as string} />}
        >
          <p className="max-h-48 overflow-auto whitespace-pre-wrap text-sm leading-relaxed text-neutral-700 dark:text-neutral-300">
            {result.cleaned_text as string}
          </p>
        </Section>
      )}
    </div>
  );
}

/* ───────────────────────────── dispatcher ──────────────────────────────── */

const VIEWS: Record<string, (p: { result: Record<string, unknown> }) => React.ReactElement> = {
  "ai-detector": AiDetectorView,
  "ai-grader": AiGraderView,
  "citation-finder": CitationFinderView,
  authorship: AuthorshipView,
  "hidden-text": HiddenTextView,
};

export function hasRichToolView(tool: string): boolean {
  return tool in VIEWS;
}

export default function RichToolResult({
  tool,
  result,
}: {
  tool: string;
  result: Record<string, unknown>;
}): React.ReactElement | null {
  const View = VIEWS[tool];
  return View ? <View result={result} /> : null;
}
