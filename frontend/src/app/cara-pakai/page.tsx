import Link from "next/link";

const STEPS = [
  {
    n: 1,
    icon: "🧭",
    title: "Pilih fitur",
    desc: "Buka menu Fitur di atas lalu pilih alat yang Anda butuhkan — Plagiarism Checker, Grammar Checker, Paraphraser, Humanizer, atau lainnya.",
  },
  {
    n: 2,
    icon: "📋",
    title: "Masukkan teks",
    desc: "Tempel teks langsung ke kotak input, atau ketik manual. Untuk pemeriksaan plagiarisme Anda juga dapat mengunggah dokumen.",
  },
  {
    n: 3,
    icon: "⚡",
    title: "Jalankan analisis",
    desc: "Klik tombol aksi. Mesin kami memproses dengan akselerasi GPU dan membandingkan ke 1 juta+ dokumen akses-terbuka.",
  },
  {
    n: 4,
    icon: "📊",
    title: "Baca & ekspor laporan",
    desc: "Lihat skor kemiripan/AI, sumber yang cocok, dan sorotan per-kalimat. Salin atau ekspor hasilnya sesuai kebutuhan.",
  },
];

const TIPS = [
  { icon: "✅", t: "Gunakan teks minimal 40 kata agar deteksi lebih akurat." },
  { icon: "🌗", t: "Ganti tema terang/gelap/sistem lewat tombol di kanan atas." },
  { icon: "🔒", t: "Dokumen diproses secara lokal (self-hosted) — privasi Anda terjaga." },
  { icon: "📑", t: "Semua sumber bersifat akses-terbuka (CC0/CC-BY), jadi 100% legal." },
];

const FAQ = [
  {
    q: "Apakah ICALORA-LABS seakurat Turnitin?",
    a: "Kami membandingkan ke korpus 1 juta+ dokumen akses-terbuka dari OpenAlex, PMC, DOAJ, dan sumber publisher lainnya, lalu akan terus bertambah. Untuk teks akademik berbahasa umum, hasilnya sangat kompetitif.",
  },
  {
    q: "Apakah data saya disimpan atau dijual?",
    a: "Tidak. Platform ini self-hosted. Teks yang Anda periksa tidak dijual atau dibagikan ke pihak ketiga.",
  },
  {
    q: "Berapa biayanya?",
    a: "Gratis. Tujuan kami menyediakan alternatif Turnitin tanpa langganan mahal.",
  },
  {
    q: "Dari mana sumber datanya?",
    a: "Hanya dari repositori akses-terbuka berlisensi CC0/CC-BY sehingga bebas masalah hak cipta.",
  },
];

export default function CaraPakaiPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-16 sm:px-6">
      <div className="text-center">
        <span className="inline-flex items-center gap-2 rounded-full border border-c bg-white/70 px-3 py-1 text-xs font-medium text-neutral-700 dark:bg-white/5 dark:text-neutral-200">
          📖 Panduan
        </span>
        <h1 className="mt-4 text-4xl font-extrabold tracking-tight text-neutral-900 dark:text-white">
          Cara <span className="text-gradient">Pakai</span>
        </h1>
        <p className="mx-auto mt-3 max-w-xl text-neutral-600 dark:text-neutral-400">
          Empat langkah sederhana untuk memeriksa integritas tulisan Anda bersama ICALORA-LABS.
        </p>
      </div>

      {/* Langkah */}
      <div className="mt-12 space-y-4">
        {STEPS.map((s) => (
          <div
            key={s.n}
            className="flex gap-5 rounded-2xl border border-c surface p-6"
          >
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl brand-grad text-xl text-white">
              {s.icon}
            </div>
            <div>
              <h3 className="flex items-center gap-2 font-semibold text-neutral-900 dark:text-white">
                <span className="text-sm text-neutral-400">Langkah {s.n}</span> · {s.title}
              </h3>
              <p className="mt-1 text-sm text-neutral-600 dark:text-neutral-400">{s.desc}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Tips */}
      <div className="mt-14">
        <h2 className="text-2xl font-bold tracking-tight text-neutral-900 dark:text-white">Tips cepat</h2>
        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          {TIPS.map((t) => (
            <div
              key={t.t}
              className="flex items-start gap-3 rounded-xl border border-c p-4"
            >
              <span className="text-xl">{t.icon}</span>
              <span className="text-sm text-neutral-700 dark:text-neutral-300">{t.t}</span>
            </div>
          ))}
        </div>
      </div>

      {/* FAQ */}
      <div className="mt-14">
        <h2 className="text-2xl font-bold tracking-tight text-neutral-900 dark:text-white">
          Pertanyaan umum
        </h2>
        <div className="mt-6 space-y-3">
          {FAQ.map((f) => (
            <details
              key={f.q}
              className="group rounded-xl border border-c p-5"
            >
              <summary className="flex cursor-pointer list-none items-center justify-between font-medium text-neutral-900 dark:text-white">
                {f.q}
                <span className="text-neutral-400 transition group-open:rotate-45">+</span>
              </summary>
              <p className="mt-3 text-sm text-neutral-600 dark:text-neutral-400">{f.a}</p>
            </details>
          ))}
        </div>
      </div>

      {/* CTA */}
      <div className="mt-14 text-center">
        <Link
          href="/features/plagiarism-checker"
          className="inline-flex items-center gap-2 rounded-xl brand-grad px-7 py-3 text-sm font-semibold text-white shadow-lg shadow-violet-500/25 transition hover:opacity-95"
        >
          🛡️ Coba Sekarang
        </Link>
      </div>
    </div>
  );
}
