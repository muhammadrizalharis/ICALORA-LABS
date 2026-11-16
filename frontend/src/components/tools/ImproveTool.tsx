"use client";

import TransformTool from "@/components/tools/TransformTool";

const GOALS = [
  { value: "", label: "otomatis" },
  { value: "lebih ringkas", label: "lebih ringkas" },
  { value: "lebih formal/baku", label: "lebih formal/baku" },
  { value: "lebih jelas & runtut", label: "lebih jelas & runtut" },
  { value: "gaya akademik", label: "gaya akademik" },
];

export default function ImproveTool() {
  return (
    <TransformTool
      tool="perbaikan-dokumen"
      textPath="/tools/improve-async"
      filePath="/tools/improve-file-async"
      submitLabel="Perbaiki Dokumen"
      textPlaceholder="Tempel dokumen yang ingin diperbaiki…"
      optionField="goal"
      optionLabel="Fokus"
      optionKind="chips"
      optionValues={GOALS}
      optionDefault=""
    />
  );
}
