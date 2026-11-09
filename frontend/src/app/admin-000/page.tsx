"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";

export default function AdminLoginPage() {
  const { user, loading, adminEnabled, adminLogin } = useAuth();
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!loading && user?.is_admin) router.replace("/dashboard");
  }, [loading, user, router]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const ok = await adminLogin(password);
      if (ok) {
        router.replace("/dashboard");
      } else {
        setError("Kata sandi salah atau super admin belum dikonfigurasi.");
      }
    } catch {
      setError("Gagal menghubungi server.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-[70vh] max-w-md flex-col items-center justify-center p-8">
      <div className="w-full rounded-2xl border border-c surface p-8 shadow-sm">
        <div className="mb-1 text-center text-[11px] uppercase tracking-widest text-neutral-400">
          Akses Terbatas
        </div>
        <h1 className="text-center text-xl font-bold text-neutral-900 dark:text-neutral-50">
          Masuk Super Admin
        </h1>
        <p className="mt-2 text-center text-sm text-neutral-500 dark:text-neutral-400">
          Halaman privat. Masukkan kata sandi admin untuk melanjutkan.
        </p>

        {adminEnabled === false ? (
          <div className="mt-6 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-300">
            Super admin belum dikonfigurasi di server (ADMIN_PASSWORD kosong).
          </div>
        ) : (
          <form onSubmit={submit} className="mt-6 space-y-3">
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Kata sandi admin"
              autoFocus
              autoComplete="current-password"
              className="w-full rounded-lg border border-c surface-2 px-4 py-3 text-sm outline-none focus:border-[color:var(--brand)]"
            />
            {error && <div className="text-xs text-red-500">{error}</div>}
            <button
              type="submit"
              disabled={busy || !password}
              className="w-full rounded-lg bg-[color:var(--brand)] px-4 py-3 text-sm font-medium text-white disabled:opacity-50"
            >
              {busy ? "Memeriksa…" : "Masuk"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
