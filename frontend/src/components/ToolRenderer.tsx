"use client";

import TextTool from "@/components/TextTool";
import PlagiarismTool from "@/components/PlagiarismTool";
import ChatTool from "@/components/tools/ChatTool";
import RewriteTool from "@/components/tools/RewriteTool";
import GraderTool from "@/components/tools/GraderTool";
import ReactionsTool from "@/components/tools/ReactionsTool";
import ResumeTool from "@/components/tools/ResumeTool";
import CitationTool from "@/components/tools/CitationTool";
import AiDetectorTool from "@/components/tools/AiDetectorTool";
import AuthorshipTool from "@/components/tools/AuthorshipTool";
import TocTool from "@/components/tools/TocTool";
import ImproveTool from "@/components/tools/ImproveTool";
import HiddenTextTool from "@/components/tools/HiddenTextTool";
import PublikasiTool from "@/components/tools/PublikasiTool";
import ChatPdfTool from "@/components/tools/ChatPdfTool";
import TranskripTool from "@/components/tools/TranskripTool";

type SimpleTool = {
  endpoint: string;
  kind: "word-count" | "text-output";
  submitLabel: string;
  outputKey?: string;
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
  "daftar-isi": TocTool,
  "perbaikan-dokumen": ImproveTool,
  "hidden-text": HiddenTextTool,
  "publikasi-jurnal": PublikasiTool,
  "chat-pdf": ChatPdfTool,
  "transkrip-audio": TranskripTool,
};

export default function ToolRenderer({ slug }: { slug: string }) {
  const simple = SIMPLE_TOOLS[slug];
  const Rich = RICH_TOOLS[slug];

  if (simple) {
    return (
      <TextTool
        endpoint={simple.endpoint}
        kind={simple.kind}
        submitLabel={simple.submitLabel}
        outputKey={simple.outputKey}
      />
    );
  }
  if (Rich) return <Rich />;
  return (
    <div className="rounded-xl border border-dashed border-c p-6 text-sm text-neutral-500 dark:text-neutral-400">
      Fitur ini belum tersedia.
    </div>
  );
}
