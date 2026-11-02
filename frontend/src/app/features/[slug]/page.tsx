import { notFound } from "next/navigation";
import { getFeature, GROUP_LABEL, FEATURES } from "@/lib/features";
import PlagiarismTool from "@/components/PlagiarismTool";
import TextTool from "@/components/TextTool";
import ChatTool from "@/components/tools/ChatTool";
import RewriteTool from "@/components/tools/RewriteTool";
import GraderTool from "@/components/tools/GraderTool";
import ReactionsTool from "@/components/tools/ReactionsTool";
import ResumeTool from "@/components/tools/ResumeTool";
import CitationTool from "@/components/tools/CitationTool";
import AiDetectorTool from "@/components/tools/AiDetectorTool";
import AuthorshipTool from "@/components/tools/AuthorshipTool";

export function generateStaticParams() {
  return FEATURES.map((f) => ({ slug: f.slug }));
}

type SimpleTool = {
  endpoint: string;
  kind: "word-count" | "text-output";
  submitLabel: string;
  outputKey?: string;
  placeholder?: string;
};

const SIMPLE_TOOLS: Record<string, SimpleTool> = {
  "word-count": { endpoint: "/tools/word-count", kind: "word-count", submitLabel: "Hitung" },
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

const RICH_TOOLS: Record<string, React.ComponentType> = {
  "plagiarism-checker": PlagiarismTool,
  "ai-chat": ChatTool,
  "ai-rewriter": RewriteTool,
  "ai-grader": GraderTool,
  "reader-reactions": ReactionsTool,
  "resume-builder": ResumeTool,
  "citation-finder": CitationTool,
  "ai-detector": AiDetectorTool,
  authorship: AuthorshipTool,
};

export default async function FeaturePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const feature = getFeature(slug);
  if (!feature) notFound();

  const simple = SIMPLE_TOOLS[feature.slug];
  const Rich = RICH_TOOLS[feature.slug];
  const isActive = Boolean(simple) || Boolean(Rich);

  return (
    <div className="mx-auto max-w-4xl p-8">
      <div className="mb-1 text-[11px] uppercase tracking-wide text-neutral-400 dark:text-neutral-500">
        {GROUP_LABEL[feature.group]} · Fase {feature.phase}
      </div>
      <h1 className="text-2xl font-bold text-neutral-900 dark:text-neutral-50">{feature.name}</h1>
      <p className="mt-2 text-neutral-500 dark:text-neutral-400">
        {isActive
          ? feature.desc
          : "Fitur ini sedang dalam tahap perencanaan. UI dan logika akan diimplementasikan sesuai roadmap."}
      </p>

      <div className="mt-6">
        {simple ? (
          <TextTool
            endpoint={simple.endpoint}
            kind={simple.kind}
            submitLabel={simple.submitLabel}
            outputKey={simple.outputKey}
            placeholder={simple.placeholder}
          />
        ) : Rich ? (
          <Rich />
        ) : (
          <div className="rounded-xl border border-dashed border-c p-6 text-sm text-neutral-500 dark:text-neutral-400">
            Placeholder antarmuka untuk <b>{feature.name}</b>.
          </div>
        )}
      </div>
    </div>
  );
}
