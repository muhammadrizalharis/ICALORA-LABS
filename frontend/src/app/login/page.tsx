"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { useAuth, googleLoginUrl } from "@/lib/auth";

export default function LoginPage() {
  const { user, loading, googleEnabled } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && user) router.replace("/dashboard");
  }, [loading, user, router]);

  return (
    <div className="mx-auto flex min-h-[70vh] max-w-md flex-col items-center justify-center p-8">
      <div className="w-full rounded-2xl border border-c surface p-8 text-center shadow-sm">
        <Image
          src="/icon.png"
          alt="ICALORA-LABS"
          width={64}
          height={64}
          className="mx-auto mb-4"
        />
        <h1 className="text-xl font-bold text-neutral-900 dark:text-neutral-50">
          Masuk ke ICALORA-LABS
        </h1>
        <p className="mt-2 text-sm text-neutral-500 dark:text-neutral-400">
          Kelola saldo, gunakan semua layanan, dan tinjau riwayat pengecekan dari satu tempat.
        </p>

        <div className="mt-6 space-y-3">
          {googleEnabled ? (
            <a
              href={googleLoginUrl()}
              className="flex w-full items-center justify-center gap-3 rounded-lg border border-c surface-2 px-4 py-3 text-sm font-medium hover:bg-neutral-50 dark:hover:bg-neutral-900"
            >
              <svg width="18" height="18" viewBox="0 0 24 24">
                <path
                  fill="#4285F4"
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                />
                <path
                  fill="#34A853"
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                />
                <path
                  fill="#FBBC05"
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z"
                />
                <path
                  fill="#EA4335"
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                />
              </svg>
              Masuk dengan Google
            </a>
          ) : (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-300">
              Login Google belum dikonfigurasi (menunggu kredensial admin).
            </div>
          )}
        </div>
        <p className="mt-4 text-xs text-neutral-400">
          Semua layanan gratis · token tak terbatas selama masa awal.
        </p>
      </div>
    </div>
  );
}
