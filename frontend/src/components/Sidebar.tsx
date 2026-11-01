"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { FEATURES, GROUP_LABEL, GROUP_COLOR, type FeatureGroup } from "@/lib/features";
import ThemeToggle from "@/components/ThemeToggle";

const GROUPS: FeatureGroup[] = ["ringan", "api", "berat"];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex w-64 shrink-0 flex-col border-r border-neutral-200 bg-neutral-50 p-4 overflow-y-auto dark:border-neutral-800 dark:bg-neutral-900">
      <Link href="/" className="mb-6 block">
        {/* Teks logo berwarna putih/silver → beri panel gelap saat tema terang
            agar tetap terbaca; di tema gelap sidebar sudah gelap. */}
        <div className="rounded-xl bg-neutral-900 p-3 dark:bg-transparent dark:p-0">
          <Image
            src="/logo.png"
            alt="ICALORA-LABS by MRH INNOVEX"
            width={1536}
            height={1024}
            priority
            className="h-auto w-full"
          />
        </div>
      </Link>

      <nav className="space-y-5">
        {GROUPS.map((group) => (
          <div key={group}>
            <div className="mb-2 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-neutral-500 dark:text-neutral-400">
              <span className={`h-2 w-2 rounded-full ${GROUP_COLOR[group]}`} />
              {GROUP_LABEL[group]}
            </div>
            <ul className="space-y-0.5">
              {FEATURES.filter((f) => f.group === group).map((f) => {
                const href = `/features/${f.slug}`;
                const active = pathname === href;
                return (
                  <li key={f.slug}>
                    <Link
                      href={href}
                      className={`block rounded-md px-3 py-1.5 text-sm transition ${
                        active
                          ? "bg-neutral-900 text-white dark:bg-neutral-100 dark:text-neutral-900"
                          : "text-neutral-700 hover:bg-neutral-200 dark:text-neutral-300 dark:hover:bg-neutral-800"
                      }`}
                    >
                      {f.name}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      <div className="mt-auto pt-6">
        <ThemeToggle />
      </div>
    </aside>
  );
}
