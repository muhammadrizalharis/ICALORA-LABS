import { apiGet, apiUpload } from "@/lib/api";

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
const MAX_POLL_MS = 20 * 60 * 1000; // dokumen besar + model dingin: beri ruang 20 menit

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

async function pollJob(jobId: string): Promise<void> {
  const deadline = Date.now() + MAX_POLL_MS;
  for (;;) {
    const job = await apiGet<JobState>(`/tools/job/${jobId}`);
    if (job.status === "done") return;
    if (job.status === "error") {
      throw new Error(job.error || "Deteksi AI gagal di server.");
    }
    if (Date.now() > deadline) {
      throw new Error("Deteksi AI melebihi batas waktu.");
    }
    await sleep(POLL_INTERVAL_MS);
  }
}

// Kirim berkas PDF ke deteksi AI di latar belakang server lalu pantau statusnya.
// Seluruh teks dianalisis tanpa pemotongan; laporan PDF berformat identik dengan
// sorotan segmen dibangun dari berkas asli — sama seperti cek plagiarisme.
export async function submitAiDetectorJob(opts: { file: File }): Promise<void> {
  const start = await apiUpload<JobStart>("/tools/ai-detect-file-async", opts.file);
  await pollJob(start.job_id);
}
