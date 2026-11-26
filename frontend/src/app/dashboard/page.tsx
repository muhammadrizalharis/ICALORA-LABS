"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { tokenView } from "@/lib/tokens";
import RecentDocuments from "@/components/RecentDocuments";

export default function DashboardHome() {
  const { user, tokenEnforcement, defaultToolCost, billing, refresh } = useAuth();
  const tv = tokenView(user, tokenEnforcement, defaultToolCost, billing);

  // Muat ulang saat membuka Beranda agar saldo setelah pemakaian terbaru tampil.
  useEffect(() => {
    refresh();
  }, [refresh]);

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
            {user?.is_admin ? "Super Admin" : user?.is_staff ? "Admin" : "Aktif"}
          </div>
          <div className="text-xs text-neutral-400">{user?.email}</div>
        </div>
        <div className="rounded-2xl border border-c surface-2 p-5">
          <div className="text-xs text-neutral-500 dark:text-neutral-400">Saldo</div>
          <div
            className={`mt-1 text-2xl font-bold ${tv.low ? "text-red-500" : ""}`}
          >
            {tv.value}
          </div>
          <div className={`text-xs ${tv.low ? "text-red-400" : "text-neutral-400"}`}>{tv.note}</div>
          {!user?.is_admin && !user?.is_demo && (
            <Link
              href="/dashboard/isi-saldo"
              className="mt-3 inline-block rounded-lg bg-[color:var(--brand)] px-3 py-1.5 text-xs font-semibold text-white hover:opacity-90"
            >
              Isi Saldo / Langganan
            </Link>
          )}
        </div>
      </div>

      <div className="mt-8">
        <RecentDocuments />
      </div>
    </div>
  );
}
