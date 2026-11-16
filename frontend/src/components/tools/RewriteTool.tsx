"use client";

import TransformTool from "@/components/tools/TransformTool";

const TONES = [
  { value: "formal", label: "Formal" },
  { value: "akademik", label: "Akademik" },
  { value: "kasual", label: "Kasual" },
  { value: "ringkas", label: "Ringkas" },
  { value: "persuasif", label: "Persuasif" },
  { value: "sederhana", label: "Sederhana" },
];

export default function RewriteTool() {
  return (
    <TransformTool
      tool="ai-rewriter"
      textPath="/tools/rewrite-async"
      filePath="/tools/rewrite-file-async"
      submitLabel="Tulis Ulang"
      textPlaceholder="Tempel teks yang ingin ditulis ulang…"
      optionField="tone"
      optionLabel="Gaya"
      optionKind="select"
      optionValues={TONES}
      optionDefault="formal"
    />
  );
}
