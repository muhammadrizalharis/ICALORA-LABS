"use client";

import Link from "next/link";
import { useAuth, googleLoginUrl } from "@/lib/auth";

/**
 * Pagar tampilan: alat hanya ditampilkan setelah masuk. Ini sekadar UX — kewajiban login
 * yang sebenarnya ditegakkan backend (semua /tools/* membalas 401 tanpa sesi).
 */
export default function LoginGate({
  name,
  children,
}: {
  name: string;
  children: React.ReactNode;
}) {
  const { user, loading, googleEnabled } = useAuth();

  if (loading) {
    return <div className="py-10 text-center text-sm text-neutral-400">Memuat…</div>;
  }
  if (user) return <>{children}</>;

  return (
    <div className="rounded-2xl border border-c surface p-8 text-center shadow-sm">
      <div className="text-3xl">🔒</div>
      <h2 className="mt-3 text-lg font-bold text-neutral-900 dark:text-neutral-50">
        Masuk dulu untuk memakai {name}
      </h2>
      <p className="mx-auto mt-2 max-w-md text-sm text-neutral-500 dark:text-neutral-400">
        Layanan ICALORA-LABS hanya untuk akun terdaftar, supaya riwayat dan laporanmu tersimpan
        di akunmu sendiri.
      </p>
      <div className="mx-auto mt-6 flex max-w-xs flex-col gap-3">
        {googleEnabled && (
          <a
            href={googleLoginUrl()}
            className="rounded-xl border border-c surface-2 px-4 py-3 text-sm font-semibold text-neutral-800 hover:bg-neutral-50 dark:text-neutral-100 dark:hover:bg-neutral-900"
          >
            Masuk dengan Google
          </a>
        )}
        <Link
          href="/login"
          className="rounded-xl brand-grad px-4 py-3 text-sm font-semibold text-white hover:opacity-95"
        >
          Masuk dengan email
        </Link>
      </div>
    </div>
  );
}
