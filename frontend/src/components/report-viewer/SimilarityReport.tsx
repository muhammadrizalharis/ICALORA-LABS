// Placeholder Similarity Report viewer (spesifikasi lengkap di docs/11).
// Implementasi penuh menyusul pada Fase 3 (Plagiarism Checker).

export default function SimilarityReportPlaceholder() {
  return (
    <div className="rounded-xl border border-dashed border-neutral-300 p-6">
      <div className="flex items-center gap-4">
        <div className="flex h-20 w-20 items-center justify-center rounded-full border-4 border-neutral-200 text-xl font-bold text-neutral-400">
          --%
        </div>
        <div>
          <div className="font-semibold text-neutral-800">Kemiripan Keseluruhan</div>
          <p className="text-sm text-neutral-500">
            Report viewer akan menampilkan skor, Match Groups, Top Sources, dan highlight
            dokumen. Spesifikasi: docs/11-report-viewer-spec.md.
          </p>
        </div>
      </div>
    </div>
  );
}
