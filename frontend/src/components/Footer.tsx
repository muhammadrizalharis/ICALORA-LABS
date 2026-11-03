import Image from "next/image";
import Link from "next/link";
import { FEATURES } from "@/lib/features";

const YEAR = new Date().getFullYear();

const activeFeatures = FEATURES.filter((f) => f.status === "active").slice(0, 6);

export default function Footer() {
  return (
    <footer className="border-t border-c surface-2">
      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-14 sm:px-6 md:grid-cols-[1.4fr_1fr_1fr_1fr]">
        {/* Brand */}
        <div>
          <div className="flex items-center gap-2.5">
            <Image src="/icon.png" alt="ICALORA-LABS" width={40} height={40} className="h-10 w-10" />
            <span className="text-lg font-extrabold tracking-tight text-neutral-900 dark:text-white">
              ICALORA<span className="text-gradient">-LABS</span>
            </span>
          </div>
          <p className="mt-4 max-w-xs text-sm leading-relaxed text-neutral-600 dark:text-neutral-400">
            Platform deteksi plagiarisme & AI yang sah dan terpercaya, self-hosted. Membandingkan
            tulisan dengan 1&nbsp;juta+ dokumen akses-terbuka — cepat, aman, dan transparan.
          </p>
          <p className="mt-4 text-xs text-neutral-500 dark:text-neutral-500">by MRH INNOVEX</p>
        </div>

        {/* Layanan */}
        <div>
          <h3 className="text-sm font-semibold text-neutral-900 dark:text-white">Layanan</h3>
          <ul className="mt-4 space-y-2.5 text-sm text-neutral-600 dark:text-neutral-400">
            {activeFeatures.map((f) => (
              <li key={f.slug}>
                <Link href={`/features/${f.slug}`} className="transition hover:text-neutral-900 dark:hover:text-white">
                  {f.name}
                </Link>
              </li>
            ))}
          </ul>
        </div>

        {/* Bantuan */}
        <div>
          <h3 className="text-sm font-semibold text-neutral-900 dark:text-white">Bantuan</h3>
          <ul className="mt-4 space-y-2.5 text-sm text-neutral-600 dark:text-neutral-400">
            <li>
              <Link href="/cara-pakai" className="transition hover:text-neutral-900 dark:hover:text-white">
                Cara Pakai
              </Link>
            </li>
            <li>
              <Link href="/metodologi" className="transition hover:text-neutral-900 dark:hover:text-white">
                Metodologi &amp; Keterbatasan
              </Link>
            </li>
            <li>
              <Link href="/#fitur" className="transition hover:text-neutral-900 dark:hover:text-white">
                Semua Fitur
              </Link>
            </li>
            <li>
              <Link href="/#cara-kerja" className="transition hover:text-neutral-900 dark:hover:text-white">
                Cara Kerja
              </Link>
            </li>
          </ul>
        </div>

        {/* Kontak */}
        <div>
          <h3 className="text-sm font-semibold text-neutral-900 dark:text-white">Kontak</h3>
          <ul className="mt-4 space-y-2.5 text-sm text-neutral-600 dark:text-neutral-400">
            <li>
              <a
                href="https://www.instagram.com/mhmmddrizal/"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 transition hover:text-neutral-900 dark:hover:text-white"
              >
                <span>📷</span> Instagram
              </a>
            </li>
            <li>
              <a
                href="https://muhammad-rizal-haris.vercel.app/"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 transition hover:text-neutral-900 dark:hover:text-white"
              >
                <span>🌐</span> Blog Pribadi
              </a>
            </li>
            <li>Indonesia 🇮🇩</li>
          </ul>
        </div>
      </div>

      <div className="border-t border-c">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-2 px-4 py-6 text-xs text-neutral-500 sm:flex-row sm:px-6 dark:text-neutral-500">
          <p>© {YEAR} ICALORA-LABS by MRH INNOVEX. Semua sumber data bersifat akses-terbuka (CC0/CC-BY).</p>
          <p>Dibuat dengan ❤️ di Indonesia</p>
        </div>
      </div>
    </footer>
  );
}
