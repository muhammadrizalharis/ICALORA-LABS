"use client";

import TransformTool from "@/components/tools/TransformTool";

export default function TocTool() {
  return (
    <TransformTool
      tool="daftar-isi"
      textPath="/tools/toc-async"
      filePath="/tools/toc-file-async"
      submitLabel="Buat Daftar Isi"
      textPlaceholder="Tempel isi dokumen untuk membuat daftar isi…"
    />
  );
}
