"use client";

import { use } from "react";
import Link from "next/link";
import { getFeature } from "@/lib/features";
import HistoryList from "@/components/HistoryList";

export default function HistoryToolPage({ params }: { params: Promise<{ tool: string }> }) {
  const { tool } = use(params);
  const feature = getFeature(tool);

  return (
    <div className="mx-auto max-w-4xl p-8">
      <Link href="/dashboard/history" className="text-xs text-neutral-400 hover:underline">
        ← Semua Riwayat
      </Link>
      <div className="mt-2 mb-1 text-[11px] uppercase tracking-wide text-neutral-400">Riwayat</div>
      <h1 className="mb-4 flex items-center gap-2 text-2xl font-bold text-neutral-900 dark:text-neutral-50">
        <span>{feature?.icon ?? "🕘"}</span> Riwayat {feature?.name ?? tool}
      </h1>
      <HistoryList tool={tool} />
    </div>
  );
}
