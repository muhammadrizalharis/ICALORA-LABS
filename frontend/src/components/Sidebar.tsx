"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { FEATURES, GROUP_LABEL, GROUP_COLOR, type FeatureGroup } from "@/lib/features";

const GROUPS: FeatureGroup[] = ["ringan", "api", "berat"];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 shrink-0 border-r border-neutral-200 bg-neutral-50 p-4 overflow-y-auto">
      <Link href="/" className="block mb-6">
        <div className="text-lg font-bold tracking-tight text-neutral-900">
          ICALORA<span className="text-rose-600">-</span>LABS
        </div>
        <div className="text-[11px] uppercase tracking-widest text-neutral-400">
          by MRH INNOVEX
        </div>
      </Link>

      <nav className="space-y-5">
        {GROUPS.map((group) => (
          <div key={group}>
            <div className="mb-2 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
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
                          ? "bg-neutral-900 text-white"
                          : "text-neutral-700 hover:bg-neutral-200"
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
    </aside>
  );
}
