// Store pekerjaan (job) level-modul untuk ICALORA-LABS.
//
// Tujuan: saat pengguna mengirim dokumen dari halaman tool, proses tetap
// berjalan walau pengguna langsung diarahkan ke Beranda. Karena store ini
// hidup di level modul (bukan di dalam komponen React), fetch tidak ikut
// dibatalkan ketika komponen tool di-unmount akibat navigasi.

import { apiGet } from "@/lib/api";

export type JobStatus = "processing" | "done" | "error";

export interface Job {
  tempId: string;
  tool: string;
  title: string;
  status: JobStatus;
  historyId?: number;
  error?: string;
  createdAt: number;
}

let jobs: Job[] = [];
let historyVersion = 0;
const listeners = new Set<() => void>();

function emit() {
  for (const l of listeners) l();
}

export function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function getJobsSnapshot(): Job[] {
  return jobs;
}

export function getHistoryVersion(): number {
  return historyVersion;
}

export function dismissJob(tempId: string) {
  jobs = jobs.filter((j) => j.tempId !== tempId);
  emit();
}

function patch(tempId: string, next: Partial<Job>) {
  jobs = jobs.map((j) => (j.tempId === tempId ? { ...j, ...next } : j));
  emit();
}

async function latestHistoryId(tool: string): Promise<number | undefined> {
  try {
    const data = await apiGet<{ items: { id: number }[] }>(
      `/auth/history?tool=${encodeURIComponent(tool)}&limit=1`,
    );
    return data.items?.[0]?.id;
  } catch {
    return undefined;
  }
}

export interface StartJobOptions {
  tool: string;
  title: string;
  run: () => Promise<unknown>;
}

export function startJob({ tool, title, run }: StartJobOptions): string {
  const tempId =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).slice(2)}`;

  jobs = [
    { tempId, tool, title, status: "processing", createdAt: Date.now() },
    ...jobs,
  ];
  emit();

  void (async () => {
    try {
      await run();
      const historyId = await latestHistoryId(tool);
      patch(tempId, { status: "done", historyId });
      historyVersion += 1;
      emit();
      // Biarkan kartu "Selesai" terlihat sejenak, lalu lebur ke daftar riwayat.
      setTimeout(() => dismissJob(tempId), 5000);
    } catch (e) {
      patch(tempId, {
        status: "error",
        error: e instanceof Error ? e.message : "Terjadi kesalahan saat memproses.",
      });
    }
  })();

  return tempId;
}

export function jobTitle(source: string, fallback = "Dokumen tanpa judul"): string {
  const clean = source.trim().replace(/\s+/g, " ");
  if (!clean) return fallback;
  const snippet = clean.slice(0, 60);
  return clean.length > 60 ? `${snippet}…` : snippet;
}
