"use client";

import TransformTool from "@/components/tools/TransformTool";

export default function HumanizerTool() {
  return (
    <TransformTool
      tool="humanizer"
      textPath="/tools/humanize-async"
      filePath="/tools/humanize-file-async"
      submitLabel="Humanize"
      textPlaceholder="Tempel teks AI yang ingin dibuat lebih alami…"
    />
  );
}
