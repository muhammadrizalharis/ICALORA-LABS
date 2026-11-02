import { API_BASE } from "@/lib/api";

export function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.rel = "noopener";
  a.style.display = "none";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}

/**
 * Kirim HTML laporan ke backend untuk dirender menjadi PDF, lalu unduh.
 * Jika render PDF gagal, jatuh kembali ke unduhan HTML agar pengguna tetap
 * mendapat laporan.
 */
export async function downloadPdfReport(filename: string, html: string): Promise<void> {
  const pdfName = filename.replace(/\.html?$/i, "") + ".pdf";
  try {
    const res = await fetch(`${API_BASE}/tools/report-pdf`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ html, filename: pdfName }),
    });
    if (!res.ok) throw new Error(`${res.status}`);
    triggerDownload(await res.blob(), pdfName);
  } catch {
    const htmlName = filename.replace(/\.pdf$/i, "") + ".html";
    triggerDownload(new Blob([html], { type: "text/html;charset=utf-8" }), htmlName);
  }
}
