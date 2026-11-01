"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";

interface IngestStatus {
  total_documents: number;
  by_source: Record<string, number>;
}

function fmt(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1).replace(/\.0$/, "")} jt`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)} rb`;
  return String(n);
}

const STATIC = [
  { label: "Fitur Terintegrasi", value: "13", live: false },
  { label: "Privasi", value: "100%", live: false },
  { label: "Biaya", value: "Gratis", live: false },
];

export default function StatsBar() {
  const [status, setStatus] = useState<IngestStatus | null>(null);

  useEffect(() => {
    apiGet<IngestStatus>("/ingest/status")
      .then(setStatus)
      .catch(() => setStatus(null));
  }, []);

  const corpus = status?.total_documents ?? null;
  const sources = status ? Object.keys(status.by_source).length : null;

  const items = [
    {
      label: "Dokumen Korpus",
      value: corpus != null ? `${fmt(corpus)}+` : "—",
      live: true,
    },
    { label: "Sumber Akses-Terbuka", value: sources != null ? `${sources}+` : "—", live: true },
    ...STATIC,
  ];

  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
      {items.map((it) => (
        <div key={it.label} className="text-center sm:text-left">
          <div className="flex items-center justify-center gap-1.5 sm:justify-start">
            <span className="text-2xl font-extrabold tracking-tight text-gradient sm:text-3xl">
              {it.value}
            </span>
            {it.live && corpus != null && (
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
              </span>
            )}
          </div>
          <div className="mt-0.5 text-xs text-neutral-500 dark:text-neutral-400">{it.label}</div>
        </div>
      ))}
    </div>
  );
}
