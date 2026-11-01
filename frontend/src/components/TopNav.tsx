"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { FEATURES, GROUP_LABEL, GROUP_COLOR, type FeatureGroup } from "@/lib/features";
import ThemeToggle from "@/components/ThemeToggle";

const GROUPS: FeatureGroup[] = ["berat", "ringan", "api"];

const NAV = [
  { href: "/", label: "Beranda" },
  { href: "/cara-pakai", label: "Cara Pakai" },
];

export default function TopNav() {
  const pathname = usePathname();
  const [megaOpen, setMegaOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  // Tutup menu saat pindah halaman.
  useEffect(() => {
    setMegaOpen(false);
    setMobileOpen(false);
  }, [pathname]);

  return (
    <header className="sticky top-0 z-50 border-b border-neutral-200/70 glass dark:border-white/10">
      <nav className="mx-auto flex h-16 max-w-6xl items-center gap-6 px-4 sm:px-6">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2.5">
          <Image src="/icon.png" alt="ICALORA-LABS" width={36} height={36} className="h-9 w-9" priority />
          <span className="text-base font-extrabold tracking-tight text-neutral-900 dark:text-white">
            ICALORA<span className="text-gradient">-LABS</span>
          </span>
        </Link>

        {/* Desktop nav */}
        <div className="hidden items-center gap-1 md:flex">
          <Link
            href="/"
            className={`rounded-lg px-3 py-2 text-sm font-medium transition hover:bg-neutral-100 dark:hover:bg-white/5 ${
              pathname === "/" ? "text-neutral-900 dark:text-white" : "text-neutral-600 dark:text-neutral-300"
            }`}
          >
            Beranda
          </Link>

          {/* Fitur mega-menu */}
          <div
            className="relative"
            onMouseEnter={() => setMegaOpen(true)}
            onMouseLeave={() => setMegaOpen(false)}
          >
            <button
              type="button"
              onClick={() => setMegaOpen((v) => !v)}
              aria-expanded={megaOpen}
              className={`flex items-center gap-1 rounded-lg px-3 py-2 text-sm font-medium transition hover:bg-neutral-100 dark:hover:bg-white/5 ${
                pathname.startsWith("/features")
                  ? "text-neutral-900 dark:text-white"
                  : "text-neutral-600 dark:text-neutral-300"
              }`}
            >
              Fitur
              <span className={`text-[10px] transition ${megaOpen ? "rotate-180" : ""}`}>▼</span>
            </button>

            {megaOpen && (
              <div className="absolute left-1/2 top-full w-[720px] max-w-[92vw] -translate-x-1/2 pt-3">
                <div className="grid grid-cols-3 gap-4 rounded-2xl border border-neutral-200 bg-white p-4 shadow-2xl dark:border-white/10 dark:bg-neutral-900">
                  {GROUPS.map((group) => (
                    <div key={group}>
                      <div className="mb-2 flex items-center gap-1.5 px-2">
                        <span className={`h-2 w-2 rounded-full ${GROUP_COLOR[group]}`} />
                        <span className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500 dark:text-neutral-400">
                          {GROUP_LABEL[group]}
                        </span>
                      </div>
                      <ul className="space-y-0.5">
                        {FEATURES.filter((f) => f.group === group).map((f) => (
                          <li key={f.slug}>
                            <Link
                              href={`/features/${f.slug}`}
                              className="flex items-start gap-2.5 rounded-lg p-2 transition hover:bg-neutral-100 dark:hover:bg-white/5"
                            >
                              <span className="text-lg leading-none">{f.icon}</span>
                              <span className="min-w-0">
                                <span className="flex items-center gap-1.5">
                                  <span className="text-sm font-medium text-neutral-900 dark:text-white">
                                    {f.name}
                                  </span>
                                  {f.status === "active" && (
                                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                                  )}
                                </span>
                                <span className="block truncate text-xs text-neutral-500 dark:text-neutral-400">
                                  {f.desc}
                                </span>
                              </span>
                            </Link>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {NAV.filter((n) => n.href !== "/").map((n) => (
            <Link
              key={n.href}
              href={n.href}
              className={`rounded-lg px-3 py-2 text-sm font-medium transition hover:bg-neutral-100 dark:hover:bg-white/5 ${
                pathname === n.href ? "text-neutral-900 dark:text-white" : "text-neutral-600 dark:text-neutral-300"
              }`}
            >
              {n.label}
            </Link>
          ))}
        </div>

        {/* Right */}
        <div className="ml-auto flex items-center gap-3">
          <div className="hidden sm:block">
            <ThemeToggle />
          </div>
          <Link
            href="/features/plagiarism-checker"
            className="hidden rounded-xl brand-grad px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-violet-500/20 transition hover:opacity-95 sm:inline-flex"
          >
            Periksa Sekarang
          </Link>

          {/* Mobile toggle */}
          <button
            type="button"
            onClick={() => setMobileOpen((v) => !v)}
            aria-label="Menu"
            className="flex h-10 w-10 items-center justify-center rounded-lg border border-neutral-200 text-neutral-700 md:hidden dark:border-white/10 dark:text-neutral-200"
          >
            {mobileOpen ? "✕" : "☰"}
          </button>
        </div>
      </nav>

      {/* Mobile panel */}
      {mobileOpen && (
        <div className="border-t border-neutral-200 bg-white px-4 py-4 md:hidden dark:border-white/10 dark:bg-neutral-950">
          <div className="mb-3 flex flex-col gap-1">
            {NAV.map((n) => (
              <Link
                key={n.href}
                href={n.href}
                className="rounded-lg px-3 py-2 text-sm font-medium text-neutral-700 hover:bg-neutral-100 dark:text-neutral-200 dark:hover:bg-white/5"
              >
                {n.label}
              </Link>
            ))}
          </div>
          <div className="mb-2 px-3 text-[11px] font-semibold uppercase tracking-wide text-neutral-400">
            Fitur
          </div>
          <div className="grid grid-cols-2 gap-1">
            {FEATURES.map((f) => (
              <Link
                key={f.slug}
                href={`/features/${f.slug}`}
                className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-neutral-700 hover:bg-neutral-100 dark:text-neutral-200 dark:hover:bg-white/5"
              >
                <span>{f.icon}</span>
                <span className="truncate">{f.name}</span>
              </Link>
            ))}
          </div>
          <div className="mt-4 flex items-center justify-between gap-3">
            <ThemeToggle />
            <Link
              href="/features/plagiarism-checker"
              className="rounded-xl brand-grad px-4 py-2 text-sm font-semibold text-white"
            >
              Periksa
            </Link>
          </div>
        </div>
      )}
    </header>
  );
}
