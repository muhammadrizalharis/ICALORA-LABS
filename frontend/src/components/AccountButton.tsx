"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth";

const BTN =
  "inline-flex items-center rounded-xl border border-c px-4 py-2 text-sm font-semibold text-neutral-700 transition hover:bg-neutral-100 dark:text-neutral-200 dark:hover:bg-white/5";

/** "Masuk" bila belum login; chip profil (avatar + nama) bila sudah, menuju dashboard. */
export default function AccountButton({ className = "" }: { className?: string }) {
  const { user, loading } = useAuth();

  // Tahan tampilan selama status login belum diketahui agar tidak berkedip "Masuk".
  if (loading) {
    return (
      <span
        aria-hidden
        className={`h-10 w-24 animate-pulse rounded-xl bg-neutral-200/60 dark:bg-white/10 ${className}`}
      />
    );
  }

  if (!user) {
    return (
      <Link href="/login" className={`${BTN} ${className}`}>
        Masuk
      </Link>
    );
  }

  const label = user.name?.trim() || user.email || "Akun";
  const first = label.split(/\s+/)[0] ?? label;
  const initial = label.charAt(0).toUpperCase();

  return (
    <Link
      href="/dashboard"
      title={`${label} — buka dashboard`}
      className={`${BTN} gap-2 py-1.5 ${className}`}
    >
      {user.picture ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={user.picture}
          alt=""
          referrerPolicy="no-referrer"
          className="h-7 w-7 rounded-full object-cover"
        />
      ) : (
        <span className="flex h-7 w-7 items-center justify-center rounded-full brand-grad text-xs font-bold text-white">
          {initial}
        </span>
      )}
      <span className="max-w-[8rem] truncate">{first}</span>
    </Link>
  );
}
