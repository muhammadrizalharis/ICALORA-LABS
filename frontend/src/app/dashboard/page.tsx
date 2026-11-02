"use client";

import Link from "next/link";
import { FEATURES, GROUP_LABEL } from "@/lib/features";
import { useAuth } from "@/lib/auth";

const activeFeatures = FEATURES.filter((f) => f.status === "active");

export default function DashboardHome() {
  const { user } = useAuth();

  return (
    <div className="mx-auto max-w-6xl p-8">
      <div className="flex items-start justify-between">
        <div>
          <div className="text-[11px] uppercase tracking-wide text-neutral-400">Beranda</div>
          <h1 className="text-2xl font-bold text-neutral-900 dark:text-neutral-50">
            Selamat datang{user?.name ? `, ${user.name.split(" ")[0]}` : ""}
          </h1>
          <p className="mt-1 text-sm text-neutral-500 dark:text-neutral-400">
            Kelola saldo, gunakan layanan, dan tinjau riwayat pengecekan dari satu tempat.
          </p>
        </div>
      </div>

      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        <div className="rounded-2xl border border-c surface-2 p-5">
          <div className="text-xs text-neutral-500 dark:text-neutral-400">Status Akun</div>
          <div className="mt-1 text-2xl font-bold text-[color:var(--brand)]">
            {user?.is_demo ? "Demo" : "Aktif"}
          </div>
          <div className="text-xs text-neutral-400">{user?.email}</div>
        </div>
        <div className="rounded-2xl border border-c surface-2 p-5">
          <div className="text-xs text-neutral-500 dark:text-neutral-400">Token / Saldo</div>
          <div className="mt-1 text-2xl font-bold">∞</div>
          <div className="text-xs text-neutral-400">Tak terbatas · semua fitur gratis</div>
        </div>
      </div>

      <h2 className="mb-3 mt-8 text-lg font-semibold">Layanan</h2>
      <p className="mb-4 text-sm text-neutral-500 dark:text-neutral-400">
        Pilih layanan untuk memulai pengecekan baru.
      </p>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {activeFeatures.map((f) => (
          <div key={f.slug} className="rounded-2xl border border-c surface-2 p-5">
            <div className="flex items-start justify-between">
              <div className="text-2xl">{f.icon}</div>
              <span className="rounded-full border border-c px-2 py-0.5 text-[10px] text-neutral-400">
                {GROUP_LABEL[f.group]}
              </span>
            </div>
            <h3 className="mt-3 font-semibold text-neutral-900 dark:text-neutral-100">{f.name}</h3>
            <p className="mt-1 line-clamp-2 text-xs text-neutral-500 dark:text-neutral-400">{f.desc}</p>
            <div className="mt-4 flex gap-2">
              <Link
                href={`/dashboard/tools/${f.slug}`}
                className="flex-1 rounded-lg bg-[color:var(--brand)] px-3 py-2 text-center text-sm font-medium text-white"
              >
                Mulai
              </Link>
              <Link
                href={`/dashboard/history/${f.slug}`}
                className="rounded-lg border border-c px-3 py-2 text-center text-sm text-neutral-600 dark:text-neutral-400"
              >
                Riwayat
              </Link>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
