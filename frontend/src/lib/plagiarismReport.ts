// Logika murni laporan kemiripan ICALORA Similarity Checker.
// Dipakai bersama oleh halaman tool (input) dan penampil riwayat (hasil),
// sehingga laporan tampil identik di mana pun dibuka.

export interface Source {
  doc_id: number | null;
  source: string;
  external_id: string;
  doi: string | null;
  title: string | null;
  pub_year: number | null;
  semantic_similarity: number;
  lexical_similarity: number;
  similarity: number;
  snippet: string;
  url?: string | null;
  online?: boolean;
  source_containment?: number;
  match_percent?: number;
  doi_identity?: boolean;
}

export interface MatchedPassage {
  sentence: string;
  match_ratio: number;
  source_title: string | null;
  source_doi: string | null;
  doc_id: number | null;
  char_len?: number;
  quoted?: boolean;
  cited?: boolean;
  in_bibliography?: boolean;
  group?: string;
}

export interface MatchGroup {
  type: string;
  count: number;
  percent: number;
}

export interface PublicationMatch {
  title: string | null;
  doi: string | null;
  url: string | null;
  source: string | null;
  containment: number;
  online: boolean;
  by_doi?: boolean;
  by_title?: boolean;
}

export interface Report {
  overall_similarity: number;
  integrity_index?: number;
  copy_similarity?: number;
  paraphrase_component?: number;
  publication_match?: PublicationMatch | null;
  document_lexical_similarity: number;
  paraphrase_similarity: number;
  similarity_index: number;
  matched_sentences: number;
  total_sentences: number;
  matched_passages: MatchedPassage[];
  match_groups?: MatchGroup[];
  document_text?: string;
  document_truncated?: boolean;
  word_count: number;
  char_count: number;
  sources: Source[];
  report_id?: string;
  content_sha256?: string;
  corpus_size?: number;
  semantic_coverage_docs?: number;
  semantic_coverage_pct?: number;
  coverage_note?: string;
  generated_at?: string;
  has_original_pdf?: boolean;
  source_filename?: string;
  online_merged?: boolean;
  online_providers?: { name: string; hits: number }[];
}

export const HILITE = [
  { bg: "#fde68a", bd: "#d97706" },
  { bg: "#bfdbfe", bd: "#2563eb" },
  { bg: "#bbf7d0", bd: "#16a34a" },
  { bg: "#fbcfe8", bd: "#db2777" },
  { bg: "#ddd6fe", bd: "#7c3aed" },
  { bg: "#fed7aa", bd: "#ea580c" },
  { bg: "#a5f3fc", bd: "#0891b2" },
  { bg: "#e9d5ff", bd: "#9333ea" },
];

// Ambang filter "Exclude" pada laporan.
export const MIN_WORDS = 8; // kecocokan < 8 kata dianggap terlalu pendek
export const MIN_PCT = 1.0; // sumber yang menyumbang < 1% dianggap kecil

// Kelompok kecocokan (Match Groups) — taksonomi orisinal ICALORA berbasis
// tingkat keparahan & sifat kecocokan (bukan status sitasi ala Turnitin).
export const MATCH_GROUP_META: Record<string, { label: string; dot: string; desc: string }> = {
  salinan_langsung: {
    label: "Salinan Langsung",
    dot: "#e11d48",
    desc: "Teks nyaris identik dengan sumber, tanpa atribusi",
  },
  kemiripan_kuat: {
    label: "Kemiripan Kuat",
    dot: "#f97316",
    desc: "Tumpang-tindih kata tinggi walau sebagian ditata ulang",
  },
  indikasi_parafrase: {
    label: "Indikasi Parafrase",
    dot: "#eab308",
    desc: "Kemiripan makna dengan sebagian kata diubah",
  },
  sumber_terkredit: {
    label: "Sumber Terkredit",
    dot: "#22c55e",
    desc: "Dikutip dan disitasi dengan benar — bukan risiko",
  },
};
export const MATCH_GROUP_ORDER = [
  "salinan_langsung",
  "kemiripan_kuat",
  "indikasi_parafrase",
  "sumber_terkredit",
];

export function escHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

export interface SrcAgg {
  key: string;
  title: string | null;
  doi: string | null;
  color: number;
  chars: number;
  count: number;
  pct: number;
  num: number;
}

export function passageKey(p: MatchedPassage): string {
  return p.source_title || (p.doc_id != null ? `doc-${p.doc_id}` : "src");
}

/** Bangun HTML dokumen dengan sorotan warna + badge nomor per sumber. */
export function buildHighlight(
  original: string,
  passages: MatchedPassage[],
  charCount: number,
  linked = false,
  opts: { minWords?: number; exclude?: Set<string> } = {},
): { html: string; sources: SrcAgg[] } {
  const minWords = opts.minWords ?? 0;
  const exclude = opts.exclude ?? new Set<string>();
  const map = new Map<string, SrcAgg>();
  const order: string[] = [];
  for (const p of passages) {
    const key = passageKey(p);
    if (exclude.has(key)) continue;
    if (!map.has(key)) {
      map.set(key, {
        key,
        title: p.source_title,
        doi: p.source_doi,
        color: order.length % HILITE.length,
        chars: 0,
        count: 0,
        pct: 0,
        num: 0,
      });
      order.push(key);
    }
  }

  const lower = original.toLowerCase();
  const ranges: { start: number; end: number; key: string }[] = [];
  for (const p of passages) {
    const key = passageKey(p);
    if (exclude.has(key)) continue;
    const needle = p.sentence.trim().toLowerCase();
    if (needle.length < 10) continue;
    if (minWords > 0 && needle.split(/\s+/).filter(Boolean).length < minWords) continue;
    let idx = lower.indexOf(needle);
    let len = needle.length;
    if (idx < 0) {
      const frag = needle.slice(0, 80);
      idx = lower.indexOf(frag);
      len = frag.length;
      if (idx < 0) continue;
    }
    ranges.push({ start: idx, end: idx + len, key });
  }

  ranges.sort((a, b) => a.start - b.start);
  const merged: { start: number; end: number; key: string }[] = [];
  let lastEnd = -1;
  for (const r of ranges) {
    if (r.start >= lastEnd) {
      merged.push(r);
      lastEnd = r.end;
    }
  }

  for (const r of merged) {
    const agg = map.get(r.key)!;
    agg.chars += r.end - r.start;
    agg.count += 1;
  }

  const sources = order
    .map((k) => {
      const a = map.get(k)!;
      a.pct = Math.round((a.chars / Math.max(charCount, 1)) * 1000) / 10;
      return a;
    })
    .filter((a) => a.count > 0)
    .sort((a, b) => b.pct - a.pct);
  sources.forEach((a, i) => {
    a.num = i + 1;
  });

  let html = "";
  let pos = 0;
  for (const r of merged) {
    if (r.start > pos) html += escHtml(original.slice(pos, r.start));
    const agg = map.get(r.key)!;
    const c = HILITE[agg.color];
    const badge = linked
      ? `<a class="hlnum" href="#src-${agg.num}" style="background:${c.bd};">${agg.num}</a>`
      : `<span class="hlnum" style="background:${c.bd};">${agg.num}</span>`;
    html += `<span class="hl" style="background:${c.bg};border-bottom:2px solid ${c.bd};">${badge}${escHtml(
      original.slice(r.start, r.end),
    )}</span>`;
    pos = r.end;
  }
  if (pos < original.length) html += escHtml(original.slice(pos));

  return { html, sources };
}

export function verdictFor(v: number): { label: string; note: string } {
  if (v >= 40)
    return {
      label: "Kemiripan tinggi",
      note: "Indeks kemiripan tinggi — banyak bagian cocok dengan sumber. Perlu ditinjau serius dan diparafrase/disitasi.",
    };
  if (v >= 15)
    return {
      label: "Kemiripan sedang",
      note: "Terdapat kemiripan pada beberapa bagian — tinjau teks yang disorot dan pastikan sudah disitasi dengan benar.",
    };
  return {
    label: "Kemiripan rendah",
    note: "Indeks kemiripan rendah — dokumen relatif orisinal terhadap korpus yang dibandingkan.",
  };
}

export function ringClass(v: number): string {
  if (v >= 40) return "c-red";
  if (v >= 15) return "c-amber";
  return "c-green";
}

export function toneForScore(v: number): string {
  if (v >= 40) return "border-red-400 text-red-600";
  if (v >= 15) return "border-amber-400 text-amber-600";
  return "border-emerald-400 text-emerald-600";
}

/** Susun HTML laporan lengkap (untuk unduh/lihat PDF). */
export function buildReportHtml(args: {
  report: Report;
  text: string;
  docTitle?: string;
  passages: MatchedPassage[];
  hiOpts: { minWords: number; exclude: Set<string> };
}): string {
  const { report, text, hiOpts } = args;
  const docTitle = args.docTitle ?? "";
  const now = new Date().toLocaleString("id-ID");
  const { html: hiText, sources: hiSources } = buildHighlight(
    text,
    args.passages,
    report.char_count,
    true,
    hiOpts,
  );
  const filtered = hiOpts.minWords > 0 || hiOpts.exclude.size > 0;
  const headline = report.integrity_index ?? report.overall_similarity;
  const idx = filtered
    ? Math.min(100, Math.round(hiSources.reduce((a, s) => a + s.pct, 0) * 10) / 10)
    : headline;
  const v = verdictFor(idx);

  const overview = hiSources
    .map((s, i) => {
      const c = HILITE[s.color];
      return `<tr id="src-${i + 1}">
  <td class="num"><span class="swatch" style="background:${c.bd};">${i + 1}</span></td>
  <td class="pct">${s.pct.toFixed(1)}%</td>
  <td>${escHtml(s.title || "(tanpa judul)")}${
    s.doi ? `<div class="src">${escHtml(s.doi)}</div>` : ""
  }<div class="src">${s.count} bagian cocok</div></td>
</tr>`;
    })
    .join("");

  const sources = report.sources
    .map(
      (s) => `<tr><td class="pct">${s.similarity.toFixed(1)}%</td><td>${escHtml(
        s.title || "(tanpa judul)",
      )}${s.online ? ` <span style="background:#0ea5e9;color:#fff;border-radius:4px;padding:0 5px;font-size:10px;font-weight:700;">DARING</span>` : ""}<div class="src">${escHtml(s.source)}${s.pub_year ? ` · ${s.pub_year}` : ""}${
        s.doi ? ` · ${escHtml(s.doi)}` : ""
      }${
        s.source_containment && s.source_containment >= 40
          ? ` · abstrak ${s.source_containment.toFixed(0)}% termuat`
          : ` · topik ${s.semantic_similarity.toFixed(0)}%`
      }</div></td></tr>`,
    )
    .join("");

  const ringCls = ringClass(idx);
  const groupsHtml =
    report.match_groups && report.match_groups.some((g) => g.count > 0)
      ? `<h2>Kelompok Kecocokan</h2><table>${MATCH_GROUP_ORDER.map((key) => {
          const g = report.match_groups?.find((x) => x.type === key);
          const meta = MATCH_GROUP_META[key];
          return `<tr><td class="num"><span class="swatch" style="background:${meta.dot};">&nbsp;</span></td><td class="pct">${(
            g?.percent ?? 0
          ).toFixed(1)}%</td><td>${escHtml(meta.label)}<div class="src">${escHtml(
            meta.desc,
          )} · ${g?.count ?? 0} bagian</div></td></tr>`;
        }).join("")}</table>`
      : "";

  return `<!doctype html><html lang="id"><head><meta charset="utf-8">
<title>Laporan Kemiripan — ICALORA-LABS</title>
<style>
  body{font-family:system-ui,Segoe UI,Roboto,sans-serif;color:#1a202c;max-width:820px;margin:28px auto;padding:0 28px;font-size:13px;line-height:1.5;}
  .head{display:flex;justify-content:space-between;align-items:flex-start;border-bottom:2px solid #0e1726;padding-bottom:12px;}
  h1{font-size:19px;margin:0;} .brand{font-size:11px;color:#64748b;margin-top:2px;}
  .sid{font-size:11px;color:#94a3b8;text-align:right;}
  .hero{display:flex;gap:22px;align-items:center;margin:22px 0 10px;}
  .ring{border:7px solid;border-radius:50%;width:112px;height:112px;display:flex;flex-direction:column;align-items:center;justify-content:center;flex:none;}
  .ring .big{font-size:30px;font-weight:800;line-height:1;} .ring .cap{font-size:9px;letter-spacing:.5px;margin-top:3px;}
  .ring.c-red{border-color:#f87171;color:#dc2626;} .ring.c-amber{border-color:#fbbf24;color:#d97706;} .ring.c-green{border-color:#34d399;color:#059669;}
  .verdict{font-size:17px;font-weight:700;} .vnote{color:#475569;font-size:12px;margin-top:4px;max-width:520px;}
  .metrics{display:flex;gap:18px;flex-wrap:wrap;margin:8px 0 4px;font-size:12px;color:#334155;}
  .metrics b{color:#0e1726;}
  h2{font-size:13px;text-transform:uppercase;letter-spacing:.6px;color:#0e1726;border-bottom:1px solid #e2e8f0;padding-bottom:6px;margin-top:26px;}
  table{width:100%;border-collapse:collapse;font-size:12px;} td{padding:7px 8px;border-bottom:1px solid #eef2f7;vertical-align:top;}
  td.pct{width:52px;font-weight:700;text-align:center;color:#0e1726;} td.num{width:30px;}
  .swatch{display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;border-radius:50%;font-size:11px;font-weight:700;color:#fff;}
  .src{color:#94a3b8;font-size:11px;margin-top:2px;}
  .doc{border:1px solid #e2e8f0;border-radius:8px;padding:14px 16px 14px 30px;font-size:12.5px;line-height:1.9;white-space:pre-wrap;word-wrap:break-word;background:#fff;}
  .hl{border-radius:2px;padding:0 1px;}
  .hlnum{display:inline-block;min-width:14px;height:14px;line-height:14px;padding:0 3px;margin:0 3px 0 -18px;border-radius:7px;color:#fff;font-size:9px;font-weight:700;text-align:center;vertical-align:middle;text-decoration:none;}
  a.hlnum{text-decoration:none;}
  .legend{font-size:11px;color:#64748b;margin:8px 0 0;}
  footer{margin-top:34px;color:#94a3b8;font-size:11px;text-align:center;border-top:1px solid #e2e8f0;padding-top:12px;}
  @media print{body{margin:0;}}
</style></head><body>
<div class="head">
  <div><h1>Laporan Indeks Kemiripan</h1><div class="brand">${
    docTitle.trim() ? `${escHtml(docTitle.trim())} · ` : ""
  }ICALORA-LABS · MRH INNOVEX — Deteksi plagiarisme yang sah &amp; terpercaya (self-hosted)</div></div>
  <div class="sid">ID Laporan: <b>${escHtml(report.report_id || "-")}</b><br>Dibuat ${escHtml(
    report.generated_at ? new Date(report.generated_at).toLocaleString("id-ID") : now,
  )}<br>Korpus akses-terbuka (CC0/CC-BY)</div>
</div>
<div class="hero">
  <div class="ring ${ringCls}"><span class="big">${
    idx > 0 && idx < 1 ? "&lt;1" : idx < 10 ? idx.toFixed(1) : idx.toFixed(0)
  }%</span><span class="cap">SIMILARITY</span></div>
  <div><div class="verdict">${v.label}</div><div class="vnote">${v.note}</div></div>
</div>
<div class="metrics">
  <div><b>${report.word_count}</b> kata</div>
  <div><b>${report.char_count}</b> karakter</div>
  <div><b>${report.matched_sentences}/${report.total_sentences}</b> kalimat cocok persis</div>
  <div><b>${report.paraphrase_similarity.toFixed(0)}%</b> risiko parafrase (semantik)</div>
  <div>deteksi salinan penuh · <b>${report.sources.length}</b> sumber teratas</div>
</div>
${report.coverage_note ? `<p class="legend">${escHtml(report.coverage_note)}</p>` : ""}
${groupsHtml}
${
  overview
    ? `<h2>Ringkasan Kecocokan (Match Overview)</h2><table>${overview}</table>`
    : `<p class="legend">Tidak ada kalimat yang cocok persis dengan sumber.</p>`
}
<h2>Dokumen dengan Sorotan</h2>
<div class="doc">${hiText || escHtml(text)}</div>
<p class="legend">Setiap teks tersorot diberi <b>penanda nomor bulat</b> sesuai sumbernya pada Ringkasan Kecocokan di atas. Klik penanda untuk melompat ke sumber terkait.</p>
<h2>Sumber Teratas</h2><table>${sources}</table>
<footer>Dibandingkan dengan korpus akses-terbuka ICALORA-LABS. ID Laporan <b>${escHtml(
    report.report_id || "-",
  )}</b> · Hash integritas SHA-256: ${escHtml(
    (report.content_sha256 || "").slice(0, 32),
  )}…<br>Laporan ini bersifat indikatif untuk tinjauan akademik, bukan vonis plagiarisme final. ID &amp; hash bersifat reproducible: teks yang sama menghasilkan ID yang sama sehingga laporan dapat diverifikasi.</footer>
</body></html>`;
}
