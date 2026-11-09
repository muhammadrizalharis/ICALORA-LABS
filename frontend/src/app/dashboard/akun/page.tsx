"use client";

import { useState } from "react";
import Image from "next/image";
import { useAuth } from "@/lib/auth";

function UserPasswordCard() {
  const { resetPassword, emailEnabled } = useAuth();
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{
    password: string;
    email: string | null;
    emailed: boolean;
    email_error: string | null;
  } | null>(null);
  const [copied, setCopied] = useState(false);
  const [failed, setFailed] = useState(false);

  async function run() {
    setBusy(true);
    setFailed(false);
    setCopied(false);
    try {
      const r = await resetPassword();
      if (r) setResult(r);
      else setFailed(true);
    } finally {
      setBusy(false);
    }
  }

  async function copy() {
    if (!result) return;
    try {
      await navigator.clipboard.writeText(result.password);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div className="mt-6 rounded-2xl border border-c surface-2 p-6">
      <h2 className="mb-1 font-semibold text-neutral-900 dark:text-neutral-50">Kata Sandi Masuk</h2>
      <p className="mb-4 text-sm text-neutral-400">
        Buat kata sandi untuk masuk dengan email. Kata sandi baru hanya ditampilkan{" "}
        <b>satu kali</b> di sini
        {emailEnabled ? " dan dikirim ke email Anda." : "."}
      </p>

      {result ? (
        <div className="space-y-3">
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 dark:border-emerald-900 dark:bg-emerald-950">
            <div className="text-xs text-emerald-700 dark:text-emerald-300">
              Kata sandi baru (simpan sekarang, tidak akan ditampilkan lagi):
            </div>
            <div className="mt-2 flex items-center gap-3">
              <code className="select-all rounded bg-white px-3 py-2 text-lg font-bold tracking-wider text-neutral-900 dark:bg-neutral-900 dark:text-neutral-50">
                {result.password}
              </code>
              <button
                onClick={copy}
                className="rounded-lg border border-c px-3 py-2 text-xs hover:bg-neutral-100 dark:hover:bg-neutral-800"
              >
                {copied ? "Tersalin" : "Salin"}
              </button>
            </div>
          </div>
          <div className="text-xs text-neutral-500 dark:text-neutral-400">
            {result.emailed
              ? `Kata sandi juga dikirim ke ${result.email}.`
              : `Tidak terkirim via email${result.email_error ? ` (${result.email_error})` : ""}. Pastikan Anda menyalinnya sekarang.`}
          </div>
          <button
            onClick={() => setResult(null)}
            className="rounded-lg border border-c px-4 py-2 text-sm text-neutral-600 hover:bg-neutral-100 dark:text-neutral-400 dark:hover:bg-neutral-800"
          >
            Selesai
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          <button
            onClick={run}
            disabled={busy}
            className="rounded-lg bg-[color:var(--brand)] px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50"
          >
            {busy ? "Membuat…" : "Buat / Reset Kata Sandi"}
          </button>
          {failed && <div className="text-xs text-red-500">Gagal membuat kata sandi. Coba lagi.</div>}
        </div>
      )}
    </div>
  );
}

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

      <UserPasswordCard />
      {user?.is_admin && <AdminPasswordCard />}
    </div>
  );
}
