"use client";

import { getFeature } from "@/lib/features";

/**
 * Banner info engine yang konsisten untuk SEMUA tool — memberi kesan rapih &
 * tepercaya, selaras dengan tema ICALORA-LABS. Pesan menyesuaikan jenis engine
 * (similarity / detektor / LLM lokal) berdasarkan grup fitur.
 */
export default function ToolEngineBanner({ slug }: { slug: string }) {
  const f = getFeature(slug);
  const engine =
    slug === "plagiarism-checker"
      ? "ICALORA Similarity Checker"
      : slug === "ai-detector"
        ? "ICALORA AI-Detector"
        : f?.group === "berat"
          ? "ICALORA Core Engine"
          : f?.group === "api"
            ? "ICALORA Corpus & API"
            : "ICALORA LLM Lokal";

  return (
    <div className="mb-5 flex items-start gap-3 rounded-xl border border-c bg-[color:var(--brand-soft)] px-4 py-3">
      <span className="text-lg">✨</span>
      <div className="text-sm">
        <div className="font-semibold text-neutral-800 dark:text-neutral-100">
          Ditenagai {engine}
        </div>
        <p className="mt-0.5 text-neutral-600 dark:text-neutral-300">
          Diproses sepenuhnya di server ICALORA-LABS (self-hosted) — dokumenmu tidak dikirim ke
          pihak ketiga. Hasil tampil instan, lengkap dengan laporan, dan tersimpan maksimal 3 hari
          sebelum dihapus otomatis.
        </p>
      </div>
    </div>
  );
}
