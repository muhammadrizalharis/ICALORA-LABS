"use client";

import TransformTool from "@/components/tools/TransformTool";

const STYLES = [
  { value: "standar", label: "Standar" },
  { value: "formal", label: "Formal" },
  { value: "akademik", label: "Akademik" },
  { value: "sederhana", label: "Sederhana" },
  { value: "kreatif", label: "Kreatif" },
];

export default function ParaphraserTool() {
  return (
    <TransformTool
      tool="paraphraser"
      textPath="/tools/paraphrase-async"
      filePath="/tools/paraphrase-file-async"
      submitLabel="Parafrase"
      textPlaceholder="Tempel teks yang ingin diparafrasekan…"
      optionField="style"
      optionLabel="Gaya"
      optionKind="select"
      optionValues={STYLES}
      optionDefault="standar"
    />
  );
}
