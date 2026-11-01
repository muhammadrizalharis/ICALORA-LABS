"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { FEATURES, GROUP_LABEL, GROUP_COLOR, type FeatureGroup } from "@/lib/features";

const GROUPS: FeatureGroup[] = ["berat", "ringan", "api"];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden w-64 shrink-0 flex-col overflow-y-auto border-r border-neutral-200 bg-neutral-50 p-4 lg:flex dark:border-neutral-800 dark:bg-neutral-900/40">
      <div className="mb-4 px-1">
        <Link
          href="/"
          className="text-xs font-medium text-neutral-500 transition hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-white"
        >
          ← Kembali ke Beranda
        </Link>
      </div>

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
                      className={`flex items-center gap-2.5 rounded-md px-3 py-1.5 text-sm transition ${
                        active
                          ? "bg-neutral-900 text-white dark:bg-neutral-100 dark:text-neutral-900"
                          : "text-neutral-700 hover:bg-neutral-200 dark:text-neutral-300 dark:hover:bg-neutral-800"
                      }`}
                    >
                      <span className="text-base leading-none">{f.icon}</span>
                      <span className="truncate">{f.name}</span>
                      {f.status === "active" && !active && (
                        <span className="ml-auto h-1.5 w-1.5 rounded-full bg-emerald-500" />
                      )}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>
    </aside>
  );
}
