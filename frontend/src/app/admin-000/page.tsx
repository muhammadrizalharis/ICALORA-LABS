"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import {
  AdminUser,
  AppSettings,
  FEATURE_LABELS,
  UserStats,
  deleteUser,
  getSettings,
  listUsers,
  patchUser,
  putSettings,
  resetUserPassword,
} from "@/lib/admin";

export default function AdminPage() {
  const { user, loading, adminEnabled, adminLogin } = useAuth();
  const isAdmin = Boolean(user?.is_admin);

  if (loading) {
    return (
      <div className="mx-auto flex min-h-[70vh] max-w-md items-center justify-center p-8 text-sm text-neutral-500">
        Memuat…
      </div>
    );
  }
  if (!isAdmin) {
    return <AdminLogin adminEnabled={adminEnabled} adminLogin={adminLogin} />;
  }
  return <AdminPanel />;
}

/* ------------------------------- LOGIN ------------------------------- */

function AdminLogin({
  adminEnabled,
  adminLogin,
}: {
  adminEnabled: boolean;
  adminLogin: (p: string) => Promise<boolean>;
}) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const ok = await adminLogin(password);
      if (!ok) setError("Kata sandi salah atau super admin belum dikonfigurasi.");
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

/* ------------------------------- PANEL ------------------------------- */

function AdminPanel() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const [tab, setTab] = useState<"users" | "settings">("users");

  return (
    <div className="mx-auto max-w-6xl p-4 sm:p-8">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-[11px] uppercase tracking-widest text-neutral-400">
            Super Admin
          </div>
          <h1 className="text-2xl font-bold text-neutral-900 dark:text-neutral-50">
            Panel Pengelolaan
          </h1>
          <p className="text-sm text-neutral-500">Masuk sebagai {user?.email}</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => router.push("/dashboard")}
            className="rounded-lg border border-c surface-2 px-4 py-2 text-sm hover:bg-neutral-50 dark:hover:bg-neutral-900"
          >
            Dashboard
          </button>
          <button
            onClick={async () => {
              await logout();
              router.push("/admin-000");
            }}
            className="rounded-lg border border-c surface-2 px-4 py-2 text-sm hover:bg-neutral-50 dark:hover:bg-neutral-900"
          >
            Keluar
          </button>
        </div>
      </div>

      <div className="mb-5 flex gap-1 border-b border-c">
        {(["users", "settings"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium ${
              tab === t
                ? "border-[color:var(--brand)] text-[color:var(--brand)]"
                : "border-transparent text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-200"
            }`}
          >
            {t === "users" ? "Pengguna" : "Pengaturan Aplikasi"}
          </button>
        ))}
      </div>

      {tab === "users" ? <UsersTab adminId={user?.id ?? -1} /> : <SettingsTab />}
    </div>
  );
}

/* ------------------------------- USERS ------------------------------- */

function UsersTab({ adminId }: { adminId: number }) {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [stats, setStats] = useState<UserStats | null>(null);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<string | null>(null);

  const load = useCallback(async (query = "") => {
    setLoading(true);
    try {
      const d = await listUsers(query);
      setUsers(d.users);
      setStats(d.stats);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Gagal memuat.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function update(id: number, fields: Partial<AdminUser>, label: string) {
    try {
      const d = await patchUser(id, fields);
      setUsers((prev) => prev.map((u) => (u.id === id ? d.user : u)));
      setMsg(`✓ ${label}`);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Gagal menyimpan.");
    }
  }

  async function removeUser(u: AdminUser) {
    if (!confirm(`Hapus pengguna ${u.email} beserta riwayatnya? Tindakan ini permanen.`)) return;
    try {
      await deleteUser(u.id);
      setUsers((prev) => prev.filter((x) => x.id !== u.id));
      setMsg(`✓ ${u.email} dihapus`);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Gagal menghapus.");
    }
  }

  async function resetPw(u: AdminUser) {
    try {
      const d = await resetUserPassword(u.id);
      setMsg(`Kata sandi baru untuk ${u.email}: ${d.password}`);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Gagal reset.");
    }
  }

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            load(q);
          }}
          className="flex gap-2"
        >
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Cari email / nama…"
            className="rounded-lg border border-c surface-2 px-3 py-2 text-sm outline-none focus:border-[color:var(--brand)]"
          />
          <button className="rounded-lg border border-c surface-2 px-4 py-2 text-sm hover:bg-neutral-50 dark:hover:bg-neutral-900">
            Cari
          </button>
        </form>
        {stats && (
          <div className="text-sm text-neutral-500">
            Total <b>{stats.total}</b> · Admin <b>{stats.admins}</b> · Nonaktif{" "}
            <b>{stats.inactive}</b>
          </div>
        )}
      </div>

      {msg && (
        <div className="mb-4 break-all rounded-lg border border-c surface-2 p-3 text-sm">
          {msg}
          <button className="ml-3 text-xs text-neutral-400 underline" onClick={() => setMsg(null)}>
            tutup
          </button>
        </div>
      )}

      {loading ? (
        <div className="p-8 text-center text-sm text-neutral-500">Memuat…</div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-c surface">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-c text-left text-xs uppercase tracking-wide text-neutral-400">
                <th className="px-3 py-3">Pengguna</th>
                <th className="px-3 py-3">Token</th>
                <th className="px-3 py-3">Admin</th>
                <th className="px-3 py-3">Status</th>
                <th className="px-3 py-3">Aksi</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-b border-c last:border-0">
                  <td className="px-3 py-3">
                    <div className="font-medium text-neutral-900 dark:text-neutral-50">
                      {u.name || "(tanpa nama)"}
                      {u.id === adminId && (
                        <span className="ml-2 rounded bg-[color:var(--brand)] px-1.5 py-0.5 text-[10px] text-white">
                          Anda
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-neutral-500">{u.email}</div>
                  </td>
                  <td className="px-3 py-3">
                    <TokenEditor
                      value={u.token_balance}
                      onSave={(v) => update(u.id, { token_balance: v }, "Token diperbarui")}
                    />
                  </td>
                  <td className="px-3 py-3">
                    <button
                      disabled={u.id === adminId}
                      onClick={() =>
                        update(u.id, { is_admin: !u.is_admin }, u.is_admin ? "Admin dicabut" : "Dijadikan admin")
                      }
                      className={`rounded-full px-3 py-1 text-xs font-medium disabled:opacity-40 ${
                        u.is_admin
                          ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
                          : "bg-neutral-100 text-neutral-500 dark:bg-neutral-800"
                      }`}
                    >
                      {u.is_admin ? "Admin" : "Bukan"}
                    </button>
                  </td>
                  <td className="px-3 py-3">
                    <button
                      disabled={u.id === adminId}
                      onClick={() =>
                        update(u.id, { is_active: !u.is_active }, u.is_active ? "Dinonaktifkan" : "Diaktifkan")
                      }
                      className={`rounded-full px-3 py-1 text-xs font-medium disabled:opacity-40 ${
                        u.is_active
                          ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
                          : "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300"
                      }`}
                    >
                      {u.is_active ? "Aktif" : "Nonaktif"}
                    </button>
                  </td>
                  <td className="px-3 py-3">
                    <div className="flex gap-2">
                      <button
                        onClick={() => resetPw(u)}
                        className="rounded-lg border border-c surface-2 px-2 py-1 text-xs hover:bg-neutral-50 dark:hover:bg-neutral-900"
                      >
                        Reset Sandi
                      </button>
                      <button
                        disabled={u.id === adminId}
                        onClick={() => removeUser(u)}
                        className="rounded-lg border border-red-200 px-2 py-1 text-xs text-red-600 hover:bg-red-50 disabled:opacity-40 dark:border-red-900 dark:hover:bg-red-950"
                      >
                        Hapus
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {users.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-3 py-8 text-center text-neutral-500">
                    Tidak ada pengguna.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function TokenEditor({ value, onSave }: { value: number; onSave: (v: number) => void }) {
  const [v, setV] = useState(String(value));
  useEffect(() => setV(String(value)), [value]);
  const changed = v !== String(value);
  return (
    <div className="flex items-center gap-1">
      <input
        type="number"
        value={v}
        min={0}
        onChange={(e) => setV(e.target.value)}
        className="w-24 rounded-lg border border-c surface-2 px-2 py-1 text-sm outline-none focus:border-[color:var(--brand)]"
      />
      {changed && (
        <button
          onClick={() => onSave(Math.max(0, parseInt(v || "0", 10)))}
          className="rounded-lg bg-[color:var(--brand)] px-2 py-1 text-xs text-white"
        >
          Simpan
        </button>
      )}
    </div>
  );
}

/* ------------------------------ SETTINGS ------------------------------ */

function SettingsTab() {
  const [s, setS] = useState<AppSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    getSettings()
      .then(setS)
      .catch((e) => setMsg(e instanceof Error ? e.message : "Gagal memuat."))
      .finally(() => setLoading(false));
  }, []);

  async function save(patch: Partial<AppSettings>) {
    if (!s) return;
    setSaving(true);
    try {
      const d = await putSettings(patch);
      setS(d.settings);
      setMsg("✓ Tersimpan");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Gagal menyimpan.");
    } finally {
      setSaving(false);
    }
  }

  function toggleFeature(slug: string, enabled: boolean) {
    if (!s) return;
    const flags = { ...s.feature_flags, [slug]: enabled };
    save({ feature_flags: flags });
  }

  if (loading || !s) {
    return <div className="p-8 text-center text-sm text-neutral-500">Memuat…</div>;
  }

  const featureEnabled = (slug: string) => s.feature_flags[slug] !== false;

  return (
    <div className="space-y-6">
      {msg && (
        <div className="rounded-lg border border-c surface-2 p-3 text-sm">
          {msg}
          <button className="ml-3 text-xs text-neutral-400 underline" onClick={() => setMsg(null)}>
            tutup
          </button>
        </div>
      )}

      <section className="rounded-xl border border-c surface p-5">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-neutral-500">
          Global
        </h2>
        <div className="space-y-4">
          <ToggleRow
            label="Mode Pemeliharaan"
            desc="Jika aktif, seluruh fitur ditutup untuk pengguna biasa (admin tetap bisa)."
            checked={s.maintenance_mode}
            disabled={saving}
            onChange={(v) => save({ maintenance_mode: v })}
            danger
          />
          <ToggleRow
            label="Pendaftaran Dibuka"
            desc="Jika nonaktif, pengguna Google baru ditolak (pengguna lama tetap bisa masuk)."
            checked={s.registration_open}
            disabled={saving}
            onChange={(v) => save({ registration_open: v })}
          />
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="font-medium text-neutral-900 dark:text-neutral-50">
                Jatah Token Default
              </div>
              <div className="text-xs text-neutral-500">
                Saldo token awal untuk setiap pengguna baru.
              </div>
            </div>
            <TokenEditor
              value={s.default_token_grant}
              onSave={(v) => save({ default_token_grant: v })}
            />
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-c surface p-5">
        <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-neutral-500">
          On/Off Fitur
        </h2>
        <p className="mb-4 text-xs text-neutral-500">
          Matikan fitur untuk menutupnya dari pengguna biasa. Super Admin tetap bisa mengaksesnya.
        </p>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {s.feature_slugs.map((slug) => (
            <label
              key={slug}
              className="flex cursor-pointer items-center justify-between rounded-lg border border-c surface-2 px-3 py-2 text-sm"
            >
              <span>{FEATURE_LABELS[slug] ?? slug}</span>
              <input
                type="checkbox"
                checked={featureEnabled(slug)}
                disabled={saving}
                onChange={(e) => toggleFeature(slug, e.target.checked)}
                className="h-4 w-4 accent-[color:var(--brand)]"
              />
            </label>
          ))}
        </div>
      </section>
    </div>
  );
}

function ToggleRow({
  label,
  desc,
  checked,
  disabled,
  onChange,
  danger,
}: {
  label: string;
  desc: string;
  checked: boolean;
  disabled?: boolean;
  onChange: (v: boolean) => void;
  danger?: boolean;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div>
        <div className="font-medium text-neutral-900 dark:text-neutral-50">{label}</div>
        <div className="text-xs text-neutral-500">{desc}</div>
      </div>
      <button
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={`relative h-6 w-11 rounded-full transition disabled:opacity-50 ${
          checked
            ? danger
              ? "bg-red-500"
              : "bg-[color:var(--brand)]"
            : "bg-neutral-300 dark:bg-neutral-700"
        }`}
      >
        <span
          className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-all ${
            checked ? "left-[22px]" : "left-0.5"
          }`}
        />
      </button>
    </div>
  );
}
