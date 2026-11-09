export type FeatureGroup = "ringan" | "api" | "berat";

export interface Feature {
  slug: string;
  name: string;
  group: FeatureGroup;
  phase: number;
  status: "planned" | "active";
  icon: string;
  desc: string;
}

// Katalog 13 fitur ICALORA-LABS (selaras dengan backend /features).
export const FEATURES: Feature[] = [
  { slug: "ai-chat", name: "AI Chat", group: "ringan", phase: 1, status: "active", icon: "💬", desc: "Asisten tulis akademik berbasis LLM lokal." },
  { slug: "grammar-checker", name: "Grammar Checker", group: "ringan", phase: 1, status: "active", icon: "✍️", desc: "Perbaiki tata bahasa & ejaan secara instan." },
  { slug: "paraphraser", name: "Paraphraser", group: "ringan", phase: 1, status: "active", icon: "🔁", desc: "Tulis ulang kalimat tetap menjaga makna." },
  { slug: "ai-rewriter", name: "AI Rewriter", group: "ringan", phase: 1, status: "active", icon: "🪄", desc: "Rombak gaya tulisan sesuai kebutuhan." },
  { slug: "humanizer", name: "Humanizer", group: "ringan", phase: 1, status: "active", icon: "🧑‍🎓", desc: "Buat teks AI terasa alami & manusiawi." },
  { slug: "ai-grader", name: "AI Grader", group: "ringan", phase: 1, status: "active", icon: "🎯", desc: "Nilai esai dengan rubrik otomatis." },
  { slug: "word-count", name: "Word Count", group: "ringan", phase: 1, status: "active", icon: "🔢", desc: "Hitung kata, kalimat, & waktu baca." },
  { slug: "citation-finder", name: "Citation Finder", group: "api", phase: 2, status: "active", icon: "🔗", desc: "Temukan & format sitasi otomatis." },
  { slug: "reader-reactions", name: "Reader Reactions", group: "ringan", phase: 1, status: "active", icon: "👀", desc: "Prediksi reaksi pembaca atas tulisan." },
  { slug: "resume-builder", name: "Resume Builder", group: "ringan", phase: 1, status: "active", icon: "📄", desc: "Susun CV profesional dalam menit." },
  { slug: "ai-detector", name: "AI Detector", group: "berat", phase: 4, status: "active", icon: "🤖", desc: "Deteksi konten buatan AI tingkat kalimat." },
  { slug: "authorship", name: "Authorship", group: "berat", phase: 4, status: "active", icon: "🕵️", desc: "Analisis gaya & verifikasi kepenulisan." },
  { slug: "plagiarism-checker", name: "Plagiarism Checker", group: "berat", phase: 3, status: "active", icon: "🛡️", desc: "Cek kemiripan dengan korpus akses-terbuka." },
  { slug: "chat-pdf", name: "Chat PDF", group: "api", phase: 2, status: "active", icon: "📚", desc: "Tanya-jawab langsung dari isi dokumen." },
  { slug: "hidden-text", name: "Cek Hidden Text & Typo", group: "ringan", phase: 1, status: "active", icon: "🔍", desc: "Deteksi karakter tersembunyi & salah ketik." },
  { slug: "daftar-isi", name: "Daftar Isi Otomatis", group: "ringan", phase: 1, status: "active", icon: "📑", desc: "Susun daftar isi berjenjang otomatis." },
  { slug: "perbaikan-dokumen", name: "Perbaikan Dokumen", group: "ringan", phase: 1, status: "active", icon: "🧹", desc: "Sunting dokumen agar rapi & baku." },
  { slug: "publikasi-jurnal", name: "Publikasi Jurnal", group: "api", phase: 2, status: "active", icon: "📰", desc: "Rekomendasi jurnal & kesiapan publikasi." },
  { slug: "transkrip-audio", name: "Transkrip Audio", group: "berat", phase: 4, status: "active", icon: "🎧", desc: "Ubah audio/video menjadi teks berwaktu." },
];

export const GROUP_LABEL: Record<FeatureGroup, string> = {
  ringan: "Fitur Ringan (LLM)",
  api: "Integrasi API",
  berat: "Fitur Inti (Berat)",
};

export const GROUP_COLOR: Record<FeatureGroup, string> = {
  ringan: "bg-emerald-500",
  api: "bg-amber-500",
  berat: "bg-rose-500",
};

export function getFeature(slug: string): Feature | undefined {
  return FEATURES.find((f) => f.slug === slug);
}
