import HistoryList from "@/components/HistoryList";

export default function HistoryAllPage() {
  return (
    <div className="mx-auto max-w-4xl p-8">
      <div className="mb-1 text-[11px] uppercase tracking-wide text-neutral-400">Riwayat</div>
      <h1 className="mb-4 text-2xl font-bold text-neutral-900 dark:text-neutral-50">Semua Riwayat</h1>
      <HistoryList />
    </div>
  );
}
