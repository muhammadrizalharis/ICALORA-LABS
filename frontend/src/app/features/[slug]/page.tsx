import { notFound } from "next/navigation";
import { getFeature, GROUP_LABEL, FEATURES } from "@/lib/features";
import SimilarityReportPlaceholder from "@/components/report-viewer/SimilarityReport";

export function generateStaticParams() {
  return FEATURES.map((f) => ({ slug: f.slug }));
}

export default async function FeaturePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const feature = getFeature(slug);
  if (!feature) notFound();

  return (
    <div className="mx-auto max-w-4xl p-8">
      <div className="mb-1 text-[11px] uppercase tracking-wide text-neutral-400">
        {GROUP_LABEL[feature.group]} · Fase {feature.phase}
      </div>
      <h1 className="text-2xl font-bold text-neutral-900">{feature.name}</h1>
      <p className="mt-2 text-neutral-500">
        Fitur ini sedang dalam tahap perencanaan. UI dan logika akan diimplementasikan
        sesuai roadmap (docs/04).
      </p>

      <div className="mt-6">
        {feature.slug === "plagiarism-checker" ? (
          <SimilarityReportPlaceholder />
        ) : (
          <div className="rounded-xl border border-dashed border-neutral-300 p-6 text-sm text-neutral-500">
            Placeholder antarmuka untuk <b>{feature.name}</b>.
          </div>
        )}
      </div>
    </div>
  );
}
