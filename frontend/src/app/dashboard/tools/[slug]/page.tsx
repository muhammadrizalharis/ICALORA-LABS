"use client";

import { use } from "react";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getFeature, GROUP_LABEL } from "@/lib/features";
import ToolRenderer from "@/components/ToolRenderer";

export default function DashboardToolPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params);
  const feature = getFeature(slug);
  if (!feature || feature.status !== "active") notFound();

  return (
    <div className="mx-auto max-w-4xl p-8">
      <Link href="/dashboard" className="text-xs text-neutral-400 hover:underline">
        ← Beranda
      </Link>
      <div className="mt-2 mb-1 text-[11px] uppercase tracking-wide text-neutral-400">
        {GROUP_LABEL[feature.group]}
      </div>
      <h1 className="flex items-center gap-2 text-2xl font-bold text-neutral-900 dark:text-neutral-50">
        <span>{feature.icon}</span> {feature.name}
      </h1>
      <p className="mt-2 text-sm text-neutral-500 dark:text-neutral-400">{feature.desc}</p>
      <div className="mt-6">
        <ToolRenderer slug={feature.slug} />
      </div>
    </div>
  );
}
