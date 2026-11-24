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
  /** ID job di server; ada pada job yang dipulihkan setelah refresh. */
  serverId?: string;
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

interface ServerJob {
  status: JobStatus;
  history_id?: number | null;
  error?: string | null;
}

const POLL_MS = 3000;
const RESUME_MAX_MS = 26 * 60 * 1000; // sedikit di atas batas keras server (25 mnt)

/**
 * Pulihkan proses yang masih berjalan di server (mis. setelah halaman di-refresh), supaya
 * Beranda tetap menampilkan "sedang diproses" lalu hasilnya, bukan daftar kosong.
 */
export async function resumeActiveJobs(): Promise<void> {
  let active: { id: string; tool: string; title: string | null; created_at: string }[] = [];
  try {
    const d = await apiGet<{ items: typeof active }>("/tools/jobs/active");
    active = d.items ?? [];
  } catch {
    return;
  }
  for (const sj of active) {
    if (jobs.some((j) => j.serverId === sj.id)) continue;
    // Job yang baru dikirim dari halaman ini sudah punya kartu lokal untuk tool yang sama.
    if (jobs.some((j) => j.status === "processing" && !j.serverId && j.tool === sj.tool)) continue;
    const tempId = `srv-${sj.id}`;
    jobs = [
      {
        tempId,
        tool: sj.tool,
        title: sj.title || "Dokumen tanpa judul",
        status: "processing",
        createdAt: Date.parse(sj.created_at) || Date.now(),
        serverId: sj.id,
      },
      ...jobs,
    ];
    emit();
    void followServerJob(tempId, sj.id);
  }
}

async function followServerJob(tempId: string, serverId: string): Promise<void> {
  const deadline = Date.now() + RESUME_MAX_MS;
  while (Date.now() < deadline) {
    await new Promise((r) => setTimeout(r, POLL_MS));
    try {
      const sj = await apiGet<ServerJob>(`/tools/job/${serverId}`);
      if (sj.status === "done") {
        patch(tempId, { status: "done", historyId: sj.history_id ?? undefined });
        historyVersion += 1;
        emit();
        setTimeout(() => dismissJob(tempId), 5000);
        return;
      }
      if (sj.status === "error") {
        patch(tempId, { status: "error", error: sj.error || "Pemeriksaan gagal di server." });
        return;
      }
    } catch {
      // Gangguan jaringan sesaat: coba lagi pada putaran berikutnya.
    }
  }
  patch(tempId, { status: "error", error: "Pemeriksaan melebihi batas waktu." });
}

export function jobTitle(source: string, fallback = "Dokumen tanpa judul"): string {
  const clean = source.trim().replace(/\s+/g, " ");
  if (!clean) return fallback;
  const snippet = clean.slice(0, 60);
  return clean.length > 60 ? `${snippet}…` : snippet;
}
