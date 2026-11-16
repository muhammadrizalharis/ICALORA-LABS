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
const MAX_POLL_MS = 20 * 60 * 1000; // dokumen besar dipecah banyak chunk + model dingin

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

async function pollJob(jobId: string): Promise<void> {
  const deadline = Date.now() + MAX_POLL_MS;
  for (;;) {
    const job = await apiGet<JobState>(`/tools/job/${jobId}`);
    if (job.status === "done") return;
    if (job.status === "error") {
      throw new Error(job.error || "Pemeriksaan tata bahasa gagal di server.");
    }
    if (Date.now() > deadline) {
      throw new Error("Pemeriksaan tata bahasa melebihi batas waktu.");
    }
    await sleep(POLL_INTERVAL_MS);
  }
}

// Kirim berkas PDF ke pemeriksaan tata bahasa di latar belakang lalu pantau.
// Seluruh teks diperiksa menyeluruh (dipecah per-chunk, tanpa pemotongan);
// laporan PDF berformat identik dengan sorotan masalah dibangun dari berkas asli.
export async function submitGrammarFileJob(opts: { file: File }): Promise<void> {
  const start = await apiUpload<JobStart>("/tools/grammar-check-file-async", opts.file);
  await pollJob(start.job_id);
}

// Versi teks tempel: diperiksa menyeluruh di latar belakang (laporan HTML).
export async function submitGrammarTextJob(opts: { text: string }): Promise<void> {
  const start = await apiPost<JobStart>("/tools/grammar-check-async", { text: opts.text });
  await pollJob(start.job_id);
}
