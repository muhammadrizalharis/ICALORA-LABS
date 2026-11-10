"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { FEATURES, GROUP_LABEL, type FeatureGroup } from "@/lib/features";

const GROUP_ORDER: FeatureGroup[] = ["berat", "api", "ringan"];

/** Tombol "Tambah baru" dengan pemilih tools (dropdown) untuk memulai
 *  pemeriksaan/dokumen baru dari dashboard. */
export default function NewDocumentMenu() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const q = query.trim().toLowerCase();
  const active = FEATURES.filter(
    (f) =>
      f.status === "active" &&
      (!q || f.name.toLowerCase().includes(q) || f.desc.toLowerCase().includes(q)),
  );

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-1.5 rounded-lg bg-[color:var(--brand)] px-3.5 py-2 text-xs font-semibold text-white transition hover:opacity-90"
      >
        <span className="text-sm leading-none">＋</span> Tambah baru
      </button>

      {open && (
        <div className="absolute right-0 z-30 mt-2 max-h-[70vh] w-80 overflow-hidden rounded-xl border border-c surface-2 shadow-xl">
          <div className="border-b border-c p-2">
            <input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Cari tool…"
              className="w-full rounded-lg border border-c surface px-3 py-2 text-xs outline-none focus:border-[color:var(--brand)]"
            />
          </div>
          <div className="thin-scrollbar max-h-[56vh] overflow-y-auto p-1.5">
            {active.length === 0 && (
              <div className="px-3 py-6 text-center text-xs text-neutral-400">
                Tool tidak ditemukan.
              </div>
            )}
            {GROUP_ORDER.map((g) => {
              const items = active.filter((f) => f.group === g);
              if (items.length === 0) return null;
              return (
                <div key={g}>
                  <div className="px-2.5 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-wider text-neutral-400">
                    {GROUP_LABEL[g]}
                  </div>
                  {items.map((f) => (
                    <Link
                      key={f.slug}
                      href={`/dashboard/tools/${f.slug}`}
                      onClick={() => setOpen(false)}
                      className="flex items-start gap-2.5 rounded-lg px-2.5 py-2 transition hover:bg-neutral-100 dark:hover:bg-neutral-900"
                    >
                      <span className="mt-0.5 w-5 shrink-0 text-center">{f.icon}</span>
                      <span className="min-w-0">
                        <span className="block text-sm font-medium text-neutral-900 dark:text-neutral-100">
                          {f.name}
                        </span>
                        <span className="block truncate text-[11px] text-neutral-400">
                          {f.desc}
                        </span>
                      </span>
                    </Link>
                  ))}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
