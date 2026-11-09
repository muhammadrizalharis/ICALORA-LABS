"use client";

import { useState } from "react";
import Image from "next/image";
import { useAuth } from "@/lib/auth";

function AdminPasswordCard() {
  const { changeAdminPassword } = useAuth();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setMsg(null);
    if (next.length < 8) {
      setMsg({ ok: false, text: "Kata sandi baru minimal 8 karakter." });
      return;
    }
    if (next !== confirm) {
      setMsg({ ok: false, text: "Konfirmasi kata sandi tidak cocok." });
      return;
    }
    setBusy(true);
    try {
      const err = await changeAdminPassword(current, next);
      if (err) {
        setMsg({ ok: false, text: err });
      } else {
        setMsg({ ok: true, text: "Kata sandi berhasil diubah." });
        setCurrent("");
        setNext("");
        setConfirm("");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-6 rounded-2xl border border-c surface-2 p-6">
      <h2 className="mb-1 font-semibold text-neutral-900 dark:text-neutral-50">Ubah Kata Sandi Admin</h2>
      <p className="mb-4 text-sm text-neutral-400">
        Kata sandi baru akan menggantikan yang tersimpan di server.
      </p>
      <form onSubmit={submit} className="space-y-3">
        <input
          type="password"
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
          placeholder="Kata sandi saat ini"
          autoComplete="current-password"
          className="w-full rounded-lg border border-c surface px-4 py-2.5 text-sm outline-none focus:border-[color:var(--brand)]"
        />
        <input
          type="password"
          value={next}
          onChange={(e) => setNext(e.target.value)}
          placeholder="Kata sandi baru (min. 8 karakter)"
          autoComplete="new-password"
          className="w-full rounded-lg border border-c surface px-4 py-2.5 text-sm outline-none focus:border-[color:var(--brand)]"
        />
        <input
          type="password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          placeholder="Ulangi kata sandi baru"
          autoComplete="new-password"
          className="w-full rounded-lg border border-c surface px-4 py-2.5 text-sm outline-none focus:border-[color:var(--brand)]"
        />
        {msg && (
          <div className={`text-xs ${msg.ok ? "text-emerald-500" : "text-red-500"}`}>{msg.text}</div>
        )}
        <button
          type="submit"
          disabled={busy || !current || !next || !confirm}
          className="rounded-lg bg-[color:var(--brand)] px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50"
        >
          {busy ? "Menyimpan…" : "Simpan kata sandi baru"}
        </button>
      </form>
    </div>
  );
}

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
            {user?.is_admin && (
              <span className="mt-1 inline-block rounded-full border border-c px-2 py-0.5 text-[10px] text-neutral-400">
                Super Admin
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

      {user?.is_admin && <AdminPasswordCard />}
    </div>
  );
}
