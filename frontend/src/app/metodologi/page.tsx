"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";

interface IngestStatus {
  total_documents: number;
  by_source?: Record<string, number>;
}

const SECTIONS = [
  {
    icon: "📚",
    title: "Sumber korpus",
    body: "Korpus pembanding dibangun sepenuhnya dari dokumen akses-terbuka: OpenAlex, PubMed Central (PMC) Open Access, DOAJ, dan metadata/abstrak publisher yang berlisensi CC0 atau CC-BY. Kami tidak menggunakan konten berbayar, berlisensi tertutup, maupun hasil scraping ilegal. Karena itu seluruh proses bersifat sah secara hukum dan dapat diaudit.",
  },
  {
    icon: "🧮",
    title: "Bagaimana kemiripan dihitung",
    body: "Setiap teks dibandingkan dengan dua lapis: (1) Leksikal/salinan — fingerprint MinHash pada shingle kata untuk mendeteksi penyalinan langsung, dan (2) Semantik/parafrase — embedding kalimat (model bge-m3, akselerasi GPU) yang dicari dengan pgvector (cosine, index HNSW) untuk menangkap parafrase. Indeks Kemiripan utama mengambil cakupan kecocokan tingkat kalimat, sementara risiko parafrase dilaporkan terpisah.",
  },
  {
    icon: "🆔",
    title: "Laporan yang dapat diverifikasi",
    body: "Setiap laporan memiliki ID Laporan deterministik berformat ICL-TANGGAL-HASH dan hash integritas SHA-256 dari teks yang diperiksa. Teks yang sama akan selalu menghasilkan ID dan hash yang sama, sehingga pihak ketiga (dosen/reviewer) dapat memverifikasi bahwa laporan tidak dimanipulasi. Jumlah dokumen pembanding dicantumkan apa adanya pada setiap laporan.",
  },
  {
    icon: "⚠️",
    title: "Keterbatasan (yang kami buka jujur)",
    body: "Korpus kami besar namun tidak mencakup seluruh karya yang pernah terbit — khususnya skripsi/tesis tak-terpublikasi, konten berlisensi tertutup, dan terbitan yang belum kami indeks. Artinya, skor kemiripan rendah TIDAK menjamin orisinalitas 100%, dan skor tinggi perlu ditinjau manusia. Laporan bersifat indikatif untuk membantu tinjauan akademik, bukan vonis plagiarisme final.",
  },
  {
    icon: "🔒",
    title: "Privasi & kedaulatan data",
    body: "Platform di-host sendiri (self-hosted) di server kami. Teks yang Anda periksa diproses secara lokal untuk analisis dan tidak dijual atau dibagikan ke pihak ketiga. Kami tidak menambahkan dokumen Anda ke korpus publik tanpa izin.",
  },
];

export default function MetodologiPage() {
  const [status, setStatus] = useState<IngestStatus | null>(null);

  useEffect(() => {
    apiGet<IngestStatus>("/ingest/status")
      .then(setStatus)
      .catch(() => setStatus(null));
  }, []);

  const total = status?.total_documents ?? 0;

  return (
    <div className="mx-auto max-w-3xl px-6 py-14">
      <div className="text-center">
        <h1 className="text-3xl font-bold text-neutral-900 dark:text-white sm:text-4xl">
          Metodologi &amp; Keterbatasan
        </h1>
        <p className="mx-auto mt-3 max-w-xl text-sm text-neutral-600 dark:text-neutral-400">
          Kami percaya alat deteksi yang terpercaya adalah alat yang transparan. Berikut cara
          kerja ICALORA-LABS secara apa adanya — termasuk apa yang <em>tidak</em> dapat kami jamin.
        </p>
      </div>

      <div className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-3">
        <div className="rounded-xl border border-c p-4 text-center">
          <div className="text-2xl font-bold text-neutral-900 dark:text-white">
            {total > 0 ? total.toLocaleString("id-ID") : "…"}
          </div>
          <div className="mt-1 text-xs text-neutral-500 dark:text-neutral-400">
            dokumen akses-terbuka
          </div>
        </div>
        <div className="rounded-xl border border-c p-4 text-center">
          <div className="text-2xl font-bold text-neutral-900 dark:text-white">CC0/CC-BY</div>
          <div className="mt-1 text-xs text-neutral-500 dark:text-neutral-400">lisensi legal</div>
        </div>
        <div className="col-span-2 rounded-xl border border-c p-4 text-center sm:col-span-1">
          <div className="text-2xl font-bold text-neutral-900 dark:text-white">2× L40S</div>
          <div className="mt-1 text-xs text-neutral-500 dark:text-neutral-400">GPU self-hosted</div>
        </div>
      </div>

      {status?.by_source && Object.keys(status.by_source).length > 0 && (
        <div className="mt-4 flex flex-wrap justify-center gap-2 text-xs">
          {Object.entries(status.by_source).map(([src, n]) => (
            <span
              key={src}
              className="rounded-full border border-c px-3 py-1 text-neutral-600 dark:text-neutral-300"
            >
              {src}: {n.toLocaleString("id-ID")}
            </span>
          ))}
        </div>
      )}

      <div className="mt-10 space-y-4">
        {SECTIONS.map((s) => (
          <div key={s.title} className="rounded-xl border border-c p-5">
            <h2 className="flex items-center gap-2 text-base font-semibold text-neutral-900 dark:text-white">
              <span>{s.icon}</span>
              {s.title}
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-neutral-600 dark:text-neutral-400">
              {s.body}
            </p>
          </div>
        ))}
      </div>

      <div className="mt-10 rounded-xl border border-amber-300 bg-amber-50 p-5 text-sm text-amber-900 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-200">
        <strong>Pernyataan integritas.</strong> ICALORA-LABS adalah platform independen oleh MRH
        INNOVEX. Kami tidak berafiliasi dengan, dan tidak mengklaim setara dengan, layanan komersial
        mana pun. Semua angka dan metodologi di halaman ini dapat diverifikasi langsung dari laporan
        yang Anda hasilkan.
      </div>

      <div className="mt-10 text-center">
        <Link
          href="/features/plagiarism-checker"
          className="inline-flex items-center gap-2 rounded-xl brand-grad px-7 py-3 text-sm font-semibold text-white shadow-lg shadow-violet-500/25 transition hover:opacity-95"
        >
          🛡️ Mulai Pemeriksaan
        </Link>
      </div>
    </div>
  );
}
