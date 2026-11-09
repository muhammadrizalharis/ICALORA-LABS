"use client";

import { useAuth } from "@/lib/auth";
import RecentDocuments from "@/components/RecentDocuments";

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
            {user?.is_admin ? "Super Admin" : "Aktif"}
          </div>
          <div className="text-xs text-neutral-400">{user?.email}</div>
        </div>
        <div className="rounded-2xl border border-c surface-2 p-5">
          <div className="text-xs text-neutral-500 dark:text-neutral-400">Token / Saldo</div>
          <div className="mt-1 text-2xl font-bold">∞</div>
          <div className="text-xs text-neutral-400">Tak terbatas · semua fitur gratis</div>
        </div>
      </div>

      <div className="mt-8">
        <RecentDocuments />
      </div>
    </div>
  );
}
