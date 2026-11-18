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
const MAX_POLL_MS = 20 * 60 * 1000; // dokumen besar + sumber daring: beri ruang 20 menit

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

async function pollJob(jobId: string): Promise<void> {
  const deadline = Date.now() + MAX_POLL_MS;
  for (;;) {
    const job = await apiGet<JobState>(`/tools/job/${jobId}`);
    if (job.status === "done") return;
    if (job.status === "error") {
      throw new Error(job.error || "Pemeriksaan gagal di server.");
    }
    if (Date.now() > deadline) {
      throw new Error("Pemeriksaan melebihi batas waktu.");
    }
    await sleep(POLL_INTERVAL_MS);
  }
}

// Kirim tugas cek plagiarisme ke latar belakang server, lalu pantau statusnya
// lewat polling. Promise ini selesai saat server merampungkan & mencatat hasil
// ke riwayat — tanpa menahan satu koneksi HTTP panjang (aman dari timeout proxy).
export interface ExcludeOpts {
  bibliography: boolean;
  quotes: boolean;
  min_source_percent: number;
}

export async function submitPlagiarismJob(opts: {
  text: string;
  file: File | null;
  topK?: number;
  exclude?: ExcludeOpts;
  /** Judul dokumen yang diisi user; disimpan sebagai judul riwayat & tampil di laporan. */
  title?: string;
}): Promise<void> {
  const topK = opts.topK ?? 30;
  const ex = opts.exclude;
  const docTitle = opts.title?.trim() ?? "";
  const start = opts.file
    ? await apiUpload<JobStart>(
        `/tools/plagiarism-file-async?top_k=${topK}` +
          (docTitle ? `&doc_title=${encodeURIComponent(docTitle)}` : "") +
          (ex
            ? `&exclude_bibliography=${ex.bibliography}&exclude_quotes=${ex.quotes}` +
              `&exclude_min_percent=${ex.min_source_percent}`
            : ""),
        opts.file,
      )
    : await apiPost<JobStart>("/tools/plagiarism-async", {
        text: opts.text,
        top_k: topK,
        ...(docTitle ? { title: docTitle } : {}),
        ...(ex ? { exclude: ex } : {}),
      });
  await pollJob(start.job_id);
}
