import Link from "next/link";
import { FEATURES, GROUP_COLOR, GROUP_LABEL, type FeatureGroup } from "@/lib/features";
import StatsBar from "@/components/StatsBar";

const GROUPS: FeatureGroup[] = ["berat", "ringan", "api"];

const STEPS = [
  {
    icon: "📋",
    title: "Tempel atau unggah",
    desc: "Salin teks atau unggah dokumen (PDF/DOCX). Tidak ada batas tersembunyi.",
  },
  {
    icon: "⚡",
    title: "Analisis dengan GPU",
    desc: "Mesin kami membandingkan ke 1 juta+ dokumen akses-terbuka dalam hitungan detik.",
  },
  {
    icon: "📊",
    title: "Laporan lengkap",
    desc: "Skor kemiripan & AI, sumber yang cocok, dan sorotan per-kalimat siap ekspor.",
  },
];

const WHY = [
  { icon: "⚖️", title: "100% Legal", desc: "Hanya korpus akses-terbuka (CC0/CC-BY). Bebas masalah hak cipta." },
  { icon: "🔒", title: "Privasi Penuh", desc: "Self-hosted. Dokumen Anda tidak pernah dijual atau dibagikan." },
  { icon: "🚀", title: "Cepat & GPU", desc: "Didukung akselerasi GPU untuk hasil nyaris seketika." },
  { icon: "💸", title: "Tanpa Biaya Mahal", desc: "Deteksi plagiarisme & AI yang sah dan terpercaya, tanpa langganan yang menguras kantong." },
];

export default function Home() {
  return (
    <div className="relative overflow-hidden">
      {/* ===== HERO ===== */}
      <section className="relative">
        <div className="pointer-events-none absolute inset-0 hero-grid" />
        <div className="glow-blob brand-grad left-[8%] top-[-60px] h-72 w-72" />
        <div className="glow-blob brand-grad right-[6%] top-[40px] h-80 w-80" style={{ animationDelay: "3s" }} />

        <div className="relative mx-auto max-w-6xl px-4 pb-16 pt-20 sm:px-6 lg:pt-28">
          <div className="grid items-center gap-12 lg:grid-cols-[1.1fr_0.9fr]">
            <div>
              <span className="inline-flex items-center gap-2 rounded-full border border-c bg-white/70 px-3 py-1 text-xs font-medium text-neutral-700 shadow-sm dark:bg-white/5 dark:text-neutral-200">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                Deteksi plagiarisme & AI yang sah, transparan & terpercaya
              </span>

              <h1 className="mt-5 text-4xl font-extrabold leading-[1.1] tracking-tight text-neutral-900 sm:text-5xl lg:text-6xl dark:text-white">
                Deteksi <span className="text-gradient">Plagiarisme & AI</span> yang akurat, cepat, dan jujur.
              </h1>

              <p className="mt-5 max-w-xl text-lg leading-relaxed text-neutral-600 dark:text-neutral-300">
                ICALORA-LABS membandingkan tulisan Anda dengan{" "}
                <strong className="text-neutral-900 dark:text-white">1 juta+ dokumen akses-terbuka</strong>{" "}
                dari jurnal & publisher global. 13 fitur integritas akademik dalam satu platform.
              </p>

              <div className="mt-8 flex flex-wrap items-center gap-3">
                <Link
                  href="/features/plagiarism-checker"
                  className="inline-flex items-center gap-2 rounded-xl brand-grad px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-violet-500/25 transition hover:opacity-95"
                >
                  🛡️ Periksa Sekarang
                </Link>
                <Link
                  href="/cara-pakai"
                  className="inline-flex items-center gap-2 rounded-xl border border-c px-6 py-3 text-sm font-semibold text-neutral-800 transition hover:bg-neutral-100 dark:border-white/15 dark:text-neutral-100 dark:hover:bg-white/5"
                >
                  Cara Pakai →
                </Link>
              </div>

              <div className="mt-10">
                <StatsBar />
              </div>
            </div>

            {/* Hero preview card */}
            <HeroPreview />
          </div>
        </div>
      </section>

      {/* ===== FITUR ===== */}
      <section id="fitur" className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-bold tracking-tight text-neutral-900 dark:text-white">
            Semua yang Anda butuhkan, <span className="text-gradient">satu platform</span>
          </h2>
          <p className="mt-3 text-neutral-600 dark:text-neutral-400">
            13 fitur terintegrasi — dari deteksi plagiarisme berat hingga asisten tulis berbasis LLM.
          </p>
        </div>

        <div className="mt-12 space-y-10">
          {GROUPS.map((group) => (
            <div key={group}>
              <div className="mb-4 flex items-center gap-2">
                <span className={`h-2.5 w-2.5 rounded-full ${GROUP_COLOR[group]}`} />
                <h3 className="text-sm font-semibold uppercase tracking-wide text-neutral-500 dark:text-neutral-400">
                  {GROUP_LABEL[group]}
                </h3>
              </div>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {FEATURES.filter((f) => f.group === group).map((f) => (
                  <Link
                    key={f.slug}
                    href={`/features/${f.slug}`}
                    className="group relative overflow-hidden rounded-2xl border border-c surface p-5 transition hover:-translate-y-0.5 hover:border-transparent hover:shadow-xl"
                  >
                    <div className="pointer-events-none absolute inset-0 opacity-0 transition group-hover:opacity-100 brand-grad-soft" />
                    <div className="relative">
                      <div className="flex items-start justify-between">
                        <span className="text-2xl">{f.icon}</span>
                        {f.status === "active" ? (
                          <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300">
                            Aktif
                          </span>
                        ) : (
                          <span className="rounded-full bg-neutral-100 px-2 py-0.5 text-[10px] font-semibold text-neutral-500 dark:bg-white/5 dark:text-neutral-400">
                            Segera
                          </span>
                        )}
                      </div>
                      <div className="mt-3 font-semibold text-neutral-900 dark:text-white">{f.name}</div>
                      <p className="mt-1 text-sm text-neutral-500 dark:text-neutral-400">{f.desc}</p>
                    </div>
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ===== CARA KERJA ===== */}
      <section id="cara-kerja" className="border-y border-c surface-2">
        <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-bold tracking-tight text-neutral-900 dark:text-white">
              Tiga langkah, <span className="text-gradient">hasil instan</span>
            </h2>
          </div>
          <div className="mt-12 grid gap-6 md:grid-cols-3">
            {STEPS.map((s, i) => (
              <div
                key={s.title}
                className="relative rounded-2xl border border-c surface p-6"
              >
                <span className="absolute right-5 top-5 text-5xl font-black text-neutral-100 dark:text-white/5">
                  {i + 1}
                </span>
                <div className="text-3xl">{s.icon}</div>
                <h3 className="mt-4 font-semibold text-neutral-900 dark:text-white">{s.title}</h3>
                <p className="mt-2 text-sm text-neutral-600 dark:text-neutral-400">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ===== KENAPA KAMI ===== */}
      <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-bold tracking-tight text-neutral-900 dark:text-white">
            Kenapa <span className="text-gradient">ICALORA-LABS</span>?
          </h2>
        </div>
        <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {WHY.map((w) => (
            <div key={w.title} className="rounded-2xl border border-c p-6">
              <div className="text-3xl">{w.icon}</div>
              <h3 className="mt-4 font-semibold text-neutral-900 dark:text-white">{w.title}</h3>
              <p className="mt-2 text-sm text-neutral-600 dark:text-neutral-400">{w.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ===== CTA ===== */}
      <section className="mx-auto max-w-6xl px-4 pb-20 sm:px-6">
        <div className="relative overflow-hidden rounded-3xl brand-grad px-8 py-14 text-center shadow-2xl">
          <div className="relative">
            <h2 className="text-3xl font-extrabold tracking-tight text-white sm:text-4xl">
              Siap memeriksa tulisan Anda?
            </h2>
            <p className="mx-auto mt-3 max-w-xl text-white/90">
              Gratis, legal, dan tanpa batas tersembunyi. Dapatkan laporan plagiarisme & AI sekarang.
            </p>
            <Link
              href="/features/plagiarism-checker"
              className="mt-8 inline-flex items-center gap-2 rounded-xl bg-white px-7 py-3 text-sm font-semibold text-neutral-900 shadow-lg transition hover:bg-neutral-100"
            >
              🛡️ Mulai Periksa Gratis
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}

function HeroPreview() {
  const score = 8;
  return (
    <div className="relative">
      <div className="glass rounded-3xl border border-c p-6 shadow-2xl">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="h-3 w-3 rounded-full bg-rose-400" />
            <span className="h-3 w-3 rounded-full bg-amber-400" />
            <span className="h-3 w-3 rounded-full bg-emerald-400" />
          </div>
          <span className="text-xs font-medium text-neutral-500 dark:text-neutral-400">Laporan Kemiripan</span>
        </div>

        <div className="mt-6 flex items-center gap-6">
          <div
            className="relative grid h-28 w-28 shrink-0 place-items-center rounded-full"
            style={{
              background: `conic-gradient(#10b981 ${score * 3.6}deg, rgba(120,140,200,0.15) 0deg)`,
            }}
          >
            <div className="grid h-[88px] w-[88px] place-items-center rounded-full surface">
              <div className="text-center">
                <div className="text-2xl font-extrabold text-emerald-500">{score}%</div>
                <div className="text-[10px] text-neutral-500">kemiripan</div>
              </div>
            </div>
          </div>
          <div className="min-w-0 flex-1 space-y-3">
            <Bar label="Teks orisinal" value={92} color="bg-emerald-500" />
            <Bar label="Kemiripan" value={8} color="bg-amber-500" />
            <Bar label="Terindikasi AI" value={3} color="bg-rose-500" />
          </div>
        </div>

        <div className="mt-6 space-y-2">
          {[
            { t: "openalex.org · Jurnal terbuka", m: "2%" },
            { t: "pmc.ncbi.nlm.nih.gov", m: "3%" },
            { t: "doaj.org · Open Access", m: "3%" },
          ].map((s) => (
            <div
              key={s.t}
              className="flex items-center justify-between rounded-lg border border-c px-3 py-2 text-xs"
            >
              <span className="truncate text-neutral-600 dark:text-neutral-300">🔗 {s.t}</span>
              <span className="ml-2 font-semibold text-amber-600 dark:text-amber-400">{s.m}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Bar({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="text-neutral-600 dark:text-neutral-400">{label}</span>
        <span className="font-semibold text-neutral-900 dark:text-white">{value}%</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-neutral-200 dark:bg-white/10">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${value}%` }} />
      </div>
    </div>
  );
}
