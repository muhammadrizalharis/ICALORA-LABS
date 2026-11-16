import { apiGet, apiPost, apiUpload } from "@/lib/api";

interface JobStart {
  job_id: string;
  status: string;
}

interface JobState {
  status: "processing" | "done" | "error";
  history_id?: number;
  error?: string;
}

const POLL_INTERVAL_MS = 2000;
const MAX_POLL_MS = 20 * 60 * 1000; // dokumen besar dipecah banyak chunk + GPU bersama

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

async function pollJob(jobId: string): Promise<void> {
  const deadline = Date.now() + MAX_POLL_MS;
  for (;;) {
    const job = await apiGet<JobState>(`/tools/job/${jobId}`);
    if (job.status === "done") return;
    if (job.status === "error") {
      throw new Error(job.error || "Proses gagal di server.");
    }
    if (Date.now() > deadline) {
      throw new Error("Proses melebihi batas waktu.");
    }
    await sleep(POLL_INTERVAL_MS);
  }
}

// Kirim teks ke alat transformasi di latar belakang (diproses menyeluruh,
// dipecah per-chunk tanpa pemotongan) lalu pantau statusnya.
export async function submitTransformTextJob(
  path: string,
  body: Record<string, unknown>,
): Promise<void> {
  const start = await apiPost<JobStart>(path, body);
  await pollJob(start.job_id);
}

// Kirim berkas PDF; laporan diff bersorotan (asli vs hasil) dibangun dari berkas.
export async function submitTransformFileJob(
  path: string,
  file: File,
  fields?: Record<string, string>,
): Promise<void> {
  const start = await apiUpload<JobStart>(path, file, fields);
  await pollJob(start.job_id);
}
