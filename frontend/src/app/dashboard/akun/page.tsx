"use client";

import Image from "next/image";
import { useAuth } from "@/lib/auth";

export default function AkunPage() {
  const { user, logout } = useAuth();

  return (
    <div className="mx-auto max-w-2xl p-8">
      <div className="mb-1 text-[11px] uppercase tracking-wide text-neutral-400">Akun</div>
      <h1 className="mb-6 text-2xl font-bold text-neutral-900 dark:text-neutral-50">Profil & Saldo</h1>

      <div className="rounded-2xl border border-c surface-2 p-6">
        <div className="flex items-center gap-4">
          {user?.picture ? (
            <Image src={user.picture} alt="" width={56} height={56} className="rounded-full" />
          ) : (
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-[color:var(--brand)] text-xl font-bold text-white">
              {(user?.name ?? user?.email ?? "U").charAt(0).toUpperCase()}
            </div>
          )}
          <div>
            <div className="font-semibold">{user?.name ?? "Pengguna"}</div>
            <div className="text-sm text-neutral-400">{user?.email}</div>
            {user?.is_demo && (
              <span className="mt-1 inline-block rounded-full border border-c px-2 py-0.5 text-[10px] text-neutral-400">
                Akun Demo
              </span>
            )}
          </div>
        </div>

        <div className="mt-6 grid grid-cols-2 gap-4">
          <div className="rounded-xl border border-c surface p-4">
            <div className="text-xs text-neutral-400">Token / Saldo</div>
            <div className="text-xl font-bold">∞</div>
          </div>
          <div className="rounded-xl border border-c surface p-4">
            <div className="text-xs text-neutral-400">Paket</div>
            <div className="text-xl font-bold">Gratis</div>
          </div>
        </div>

        <button
          onClick={logout}
          className="mt-6 w-full rounded-lg border border-c px-4 py-2 text-sm text-neutral-600 hover:bg-neutral-100 dark:text-neutral-400 dark:hover:bg-neutral-900"
        >
          Keluar dari akun
        </button>
      </div>
    </div>
  );
}
