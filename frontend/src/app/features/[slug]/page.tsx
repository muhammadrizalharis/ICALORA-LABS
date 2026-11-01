import { notFound } from "next/navigation";
import { getFeature, GROUP_LABEL, FEATURES } from "@/lib/features";
import PlagiarismTool from "@/components/PlagiarismTool";
import TextTool from "@/components/TextTool";

export function generateStaticParams() {
  return FEATURES.map((f) => ({ slug: f.slug }));
}

type ToolConfig = {
  endpoint: string;
  kind: "word-count" | "text-output";
  submitLabel: string;
  outputKey?: string;
  placeholder?: string;
};

const TOOL_CONFIG: Record<string, ToolConfig> = {
  "word-count": {
    endpoint: "/tools/word-count",
    kind: "word-count",
    submitLabel: "Hitung",
  },
  "grammar-checker": {
    endpoint: "/tools/grammar-check",
    kind: "text-output",
    submitLabel: "Periksa Tata Bahasa",
    outputKey: "corrected",
  },
  paraphraser: {
    endpoint: "/tools/paraphrase",
    kind: "text-output",
    submitLabel: "Parafrase",
    outputKey: "result",
  },
  humanizer: {
    endpoint: "/tools/humanize",
    kind: "text-output",
    submitLabel: "Humanize",
    outputKey: "result",
  },
};

export default async function FeaturePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const feature = getFeature(slug);
  if (!feature) notFound();

  const tool = TOOL_CONFIG[feature.slug];
  const isActive = Boolean(tool) || feature.slug === "plagiarism-checker";

  return (
    <div className="mx-auto max-w-4xl p-8">
      <div className="mb-1 text-[11px] uppercase tracking-wide text-neutral-400 dark:text-neutral-500">
        {GROUP_LABEL[feature.group]} · Fase {feature.phase}
      </div>
      <h1 className="text-2xl font-bold text-neutral-900 dark:text-neutral-50">{feature.name}</h1>
      <p className="mt-2 text-neutral-500 dark:text-neutral-400">
        {isActive
          ? "Masukkan teks Anda, lalu proses menggunakan mesin ICALORA-LABS."
          : "Fitur ini sedang dalam tahap perencanaan. UI dan logika akan diimplementasikan sesuai roadmap (docs/04)."}
      </p>

      <div className="mt-6">
        {tool ? (
          <TextTool
            endpoint={tool.endpoint}
            kind={tool.kind}
            submitLabel={tool.submitLabel}
            outputKey={tool.outputKey}
            placeholder={tool.placeholder}
          />
        ) : feature.slug === "plagiarism-checker" ? (
          <PlagiarismTool />
        ) : (
          <div className="rounded-xl border border-dashed border-neutral-300 p-6 text-sm text-neutral-500 dark:border-neutral-700 dark:text-neutral-400">
            Placeholder antarmuka untuk <b>{feature.name}</b>.
          </div>
        )}
      </div>
    </div>
  );
}
