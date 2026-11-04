import { downloadPdfReport, escapeHtml } from "@/lib/download";

export { escapeHtml };

export interface ReportMeta {
  reportId: string;
  hash: string;
  generatedAt: string;
}

function pad(n: number): string {
  return n.toString().padStart(2, "0");
}

/**
 * Metadata laporan yang dapat diverifikasi, konsisten di semua fitur.
 * ID bersifat deterministik: teks + tanggal yang sama menghasilkan ID yang sama,
 * sehingga laporan dapat diverifikasi ulang (anti-manipulasi).
 */
export async function reportMeta(source: string): Promise<ReportMeta> {
  const now = new Date();
  const ymd = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}`;
  let hex = "";
  try {
    const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(source));
    hex = Array.from(new Uint8Array(buf))
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
  } catch {
    // Fallback non-kriptografis bila SubtleCrypto tak tersedia (konteks tak aman).
    let h = 0;
    for (let i = 0; i < source.length; i++) h = (Math.imul(31, h) + source.charCodeAt(i)) | 0;
    hex = (h >>> 0).toString(16).padStart(8, "0").repeat(8);
  }
  return {
    reportId: `ICL-${ymd}-${hex.slice(0, 10).toUpperCase()}`,
    hash: hex,
    generatedAt: now.toISOString(),
  };
}

export interface ReportShellOpts {
  /** Judul besar laporan, mis. "Laporan Perbaikan Dokumen". */
  title: string;
  /** Isi laporan (HTML sudah ter-escape oleh pemanggil). */
  bodyHtml: string;
  meta: ReportMeta;
  /** Kalimat disclaimer profesional (opsional, ada default yang netral). */
  disclaimer?: string;
}

const BRAND = "ICALORA-LABS · MRH INNOVEX — platform akademik yang sah & terpercaya (self-hosted)";

const DEFAULT_DISCLAIMER =
  "Laporan ini dihasilkan otomatis sebagai bahan bantu akademik dan ditinjau bersama " +
  "konteks karya. ID Laporan & hash bersifat reproducible sehingga laporan dapat diverifikasi.";

/**
 * Bungkus isi laporan dengan header & footer yang konsisten untuk SEMUA fitur:
 * branding, ID Laporan terverifikasi, timestamp, dan hash integritas SHA-256.
 */
export function reportShell(opts: ReportShellOpts): string {
  const { title, bodyHtml, meta } = opts;
  const disclaimer = opts.disclaimer ?? DEFAULT_DISCLAIMER;
  const created = new Date(meta.generatedAt).toLocaleString("id-ID");
  return `<!doctype html><html lang="id"><head><meta charset="utf-8">
<title>${escapeHtml(title)} — ICALORA-LABS</title>
<style>
  body{font-family:system-ui,Segoe UI,Roboto,sans-serif;color:#1a202c;max-width:820px;margin:28px auto;padding:0 28px;font-size:13px;line-height:1.55;}
  .head{display:flex;justify-content:space-between;align-items:flex-start;border-bottom:2px solid #0e1726;padding-bottom:12px;gap:16px;}
  h1{font-size:19px;margin:0;} .brand{font-size:11px;color:#64748b;margin-top:3px;}
  .sid{font-size:10.5px;color:#94a3b8;text-align:right;line-height:1.5;min-width:210px;}
  .sid b{color:#475569;}
  h2{font-size:13px;text-transform:uppercase;letter-spacing:.6px;color:#0e1726;border-bottom:1px solid #e2e8f0;padding-bottom:6px;margin-top:26px;}
  table{width:100%;border-collapse:collapse;font-size:12px;} td,th{padding:7px 8px;border-bottom:1px solid #eef2f7;vertical-align:top;text-align:left;}
  th{font-size:11px;text-transform:uppercase;letter-spacing:.4px;color:#64748b;}
  td.r{width:88px;font-weight:700;text-align:right;}
  ul{font-size:12.5px;padding-left:18px;margin:8px 0;} li{margin:5px 0;}
  .doc{border:1px solid #e2e8f0;border-radius:8px;padding:14px 16px;font-size:12.5px;line-height:1.75;white-space:pre-wrap;word-wrap:break-word;background:#fff;}
  .doc .hl{background:#fde68a;border-bottom:2px solid #f59e0b;border-radius:2px;padding:0 1px;}
  .pill{display:inline-block;border:1px solid #e2e8f0;border-radius:999px;padding:2px 10px;font-size:11px;color:#475569;margin:0 4px 4px 0;}
  .pill-ok{background:#ecfdf5;border-color:#a7f3d0;color:#047857;}
  .pill-warn{background:#fffbeb;border-color:#fde68a;color:#b45309;}
  .pill-bad{background:#fef2f2;border-color:#fecaca;color:#b91c1c;}
  .summary{margin:14px 0;font-size:16px;font-weight:600;}
  .muted{color:#94a3b8;font-size:11px;}
  .mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;}
  footer{margin-top:34px;color:#94a3b8;font-size:10.5px;text-align:center;border-top:1px solid #e2e8f0;padding-top:12px;line-height:1.6;}
  @media print{body{margin:0;}}
</style></head><body>
<div class="head">
  <div><h1>${escapeHtml(title)}</h1><div class="brand">${BRAND}</div></div>
  <div class="sid">ID Laporan: <b class="mono">${escapeHtml(meta.reportId)}</b><br>
    Dibuat ${escapeHtml(created)}<br>
    Hash SHA-256: <span class="mono">${escapeHtml(meta.hash.slice(0, 32))}…</span></div>
</div>
${bodyHtml}
<footer>${escapeHtml(disclaimer)}<br>ID Laporan <b>${escapeHtml(
    meta.reportId,
  )}</b> · Verifikasi hash <span class="mono">${escapeHtml(
    meta.hash.slice(0, 16),
  )}…</span></footer>
</body></html>`;
}

/**
 * Jalan pintas: susun laporan dengan shell standar lalu unduh sebagai PDF.
 */
export async function buildAndDownloadReport(opts: {
  filename: string;
  title: string;
  source: string;
  bodyHtml: string;
  disclaimer?: string;
}): Promise<void> {
  const meta = await reportMeta(opts.source);
  const html = reportShell({
    title: opts.title,
    bodyHtml: opts.bodyHtml,
    meta,
    disclaimer: opts.disclaimer,
  });
  await downloadPdfReport(opts.filename, html);
}
