"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth, type Packages, type PaymentInfo } from "@/lib/auth";
import {
  ActivityItem,
  AdminUser,
  AnalyticsOverview,
  AppSettings,
  AuditItem,
  FEATURE_LABELS,
  HistoryItem,
  UserStats,
  deleteUser,
  getActivity,
  getAnalytics,
  getSettings,
  giveTokens,
  setSubscription,
  listAudit,
  listUsers,
  patchUser,
  putSettings,
  resetUserPassword,
  userHistory,
} from "@/lib/admin";

export default function AdminPage() {
  const { user, loading, adminEnabled, adminLogin } = useAuth();
  // Super Admin (tunggal) atau admin biasa boleh membuka panel; isinya dibedakan per peran.
  const canOpen = Boolean(user?.is_admin || user?.is_staff);

  if (loading) {
    return (
      <div className="mx-auto flex min-h-[70vh] max-w-md items-center justify-center p-8 text-sm text-neutral-500">
        Memuat…
      </div>
    );
  }
  if (!canOpen) {
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
        <p className="mt-1 text-center text-xs text-neutral-400">
          Admin biasa: masuk dulu lewat halaman{" "}
          <a href="/login" className="underline">
            Masuk
          </a>{" "}
          (Google/email), lalu buka halaman ini lagi.
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
  const isSuper = Boolean(user?.is_admin);
  type Tab = "aktivitas" | "users" | "audit" | "settings";
  const tabs: Tab[] = isSuper ? ["aktivitas", "users", "audit", "settings"] : ["users"];
  const [tab, setTab] = useState<Tab>(isSuper ? "aktivitas" : "users");

  return (
    <div className="mx-auto max-w-6xl p-4 sm:p-8">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-[11px] uppercase tracking-widest text-neutral-400">
            {isSuper ? "Super Admin" : "Admin"}
          </div>
          <h1 className="text-2xl font-bold text-neutral-900 dark:text-neutral-50">
            {isSuper ? "Panel Pengelolaan" : "Panel Admin"}
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
              router.push("/admin=-000");
            }}
            className="rounded-lg border border-c surface-2 px-4 py-2 text-sm hover:bg-neutral-50 dark:hover:bg-neutral-900"
          >
            Keluar
          </button>
        </div>
      </div>

      <div className="mb-5 flex gap-1 border-b border-c">
        {tabs.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium ${
              tab === t
                ? "border-[color:var(--brand)] text-[color:var(--brand)]"
                : "border-transparent text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-200"
            }`}
          >
            {t === "aktivitas"
              ? "Aktivitas"
              : t === "users"
                ? "Pengguna"
                : t === "audit"
                  ? "Log Tindakan"
                  : "Pengaturan Aplikasi"}
          </button>
        ))}
      </div>

      {!isSuper && (
        <div className="mb-4 rounded-lg border border-c surface-2 p-3 text-xs text-neutral-500">
          Sebagai <b>Admin</b>, kamu dapat melihat pengguna dan <b>menambah saldo</b> (setelah
          pembayaran DANA dikonfirmasi) serta <b>mengaktifkan langganan</b> untuk pengguna biasa
          (ada batas per pemberian, dan setiap tindakan tercatat). Pengaturan,
          peran, dan data dokumen pengguna hanya bisa diakses Super Admin.
        </div>
      )}

      {tab === "aktivitas" && isSuper ? (
        <ActivityTab />
      ) : tab === "users" ? (
        <UsersTab adminId={user?.id ?? -1} isSuper={isSuper} />
      ) : tab === "audit" && isSuper ? (
        <AuditTab />
      ) : (
        <SettingsTab />
      )}
    </div>
  );
}

/* ------------------------------ AKTIVITAS ---------------------------- */

function fmtNum(n: number): string {
  return new Intl.NumberFormat("id-ID").format(n);
}

function timeAgo(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso).getTime();
  if (Number.isNaN(d)) return "—";
  const s = Math.max(0, Math.floor((Date.now() - d) / 1000));
  if (s < 60) return `${s} dtk lalu`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} mnt lalu`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} jam lalu`;
  const dd = Math.floor(h / 24);
  if (dd < 30) return `${dd} hari lalu`;
  return new Date(iso).toLocaleDateString("id-ID");
}

function toolLabel(slug: string): string {
  return FEATURE_LABELS[slug] ?? slug;
}

const STAT_GRADIENTS = [
  "from-sky-500/15 to-blue-500/5 text-sky-600 dark:text-sky-400",
  "from-emerald-500/15 to-green-500/5 text-emerald-600 dark:text-emerald-400",
  "from-violet-500/15 to-purple-500/5 text-violet-600 dark:text-violet-400",
  "from-amber-500/15 to-orange-500/5 text-amber-600 dark:text-amber-400",
  "from-rose-500/15 to-pink-500/5 text-rose-600 dark:text-rose-400",
  "from-cyan-500/15 to-teal-500/5 text-cyan-600 dark:text-cyan-400",
];

function StatCard({
  idx,
  label,
  value,
  sub,
  icon,
}: {
  idx: number;
  label: string;
  value: string;
  sub?: string;
  icon: string;
}) {
  return (
    <div
      className={`relative overflow-hidden rounded-2xl border border-c bg-gradient-to-br ${STAT_GRADIENTS[idx % STAT_GRADIENTS.length]} p-4`}
    >
      <div className="flex items-start justify-between">
        <div className="text-[11px] font-medium uppercase tracking-wider text-neutral-500">
          {label}
        </div>
        <span className="text-lg leading-none opacity-80">{icon}</span>
      </div>
      <div className="mt-2 text-2xl font-bold text-neutral-900 dark:text-neutral-50">
        {value}
      </div>
      {sub ? <div className="mt-0.5 text-xs text-neutral-500">{sub}</div> : null}
    </div>
  );
}

function ActivityTab() {
  const [days, setDays] = useState(14);
  const [data, setData] = useState<AnalyticsOverview | null>(null);
  const [feed, setFeed] = useState<ActivityItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [toolFilter, setToolFilter] = useState<string>("");

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const [a, f] = await Promise.all([
        getAnalytics(days),
        getActivity(60, toolFilter || undefined),
      ]);
      setData(a);
      setFeed(f.items);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Gagal memuat analitik.");
    } finally {
      setLoading(false);
    }
  }, [days, toolFilter]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- muat data saat mount (fetch)
    load();
  }, [load]);

  if (loading && !data) {
    return (
      <div className="py-16 text-center text-sm text-neutral-500">Memuat analitik…</div>
    );
  }
  if (err) {
    return (
      <div className="rounded-xl border border-red-300 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300">
        {err}
      </div>
    );
  }
  if (!data) return null;

  const t = data.totals;
  const maxTool = Math.max(1, ...data.per_tool.map((x) => x.count));
  const maxDaily = Math.max(1, ...data.daily.map((x) => x.runs));
  const errPct = Math.round((data.jobs.error_rate || 0) * 1000) / 10;

  return (
    <div className="space-y-6">
      {/* kontrol rentang */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="text-sm text-neutral-500">
          Ringkasan {data.days} hari terakhir
        </div>
        <div className="flex items-center gap-2">
          {[7, 14, 30, 90].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`rounded-lg border px-3 py-1.5 text-xs font-medium ${
                days === d
                  ? "border-[color:var(--brand)] text-[color:var(--brand)]"
                  : "border-c text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-200"
              }`}
            >
              {d} hr
            </button>
          ))}
          <button
            onClick={load}
            className="rounded-lg border border-c px-3 py-1.5 text-xs font-medium text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-200"
          >
            ⟳ Segarkan
          </button>
        </div>
      </div>

      {/* kartu statistik */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
        <StatCard idx={0} label="Analisis (window)" value={fmtNum(t.runs_window)} sub={`${fmtNum(t.runs)} total`} icon="⚡" />
        <StatCard idx={1} label="Pengguna aktif" value={fmtNum(t.active_users_window)} sub={`dari ${fmtNum(t.users)} total`} icon="👥" />
        <StatCard idx={2} label="Pengguna baru" value={fmtNum(t.new_users_window)} sub="pendaftaran baru" icon="✨" />
        <StatCard idx={3} label="Saldo beredar" value={"Rp" + fmtNum(t.tokens_outstanding)} sub="saldo seluruh user" icon="🪙" />
        <StatCard idx={4} label="Job async" value={fmtNum(data.jobs.total)} sub={`${Object.keys(data.jobs.by_status).length} status`} icon="⚙️" />
        <StatCard idx={5} label="Error rate" value={`${errPct}%`} sub={`${fmtNum(data.jobs.by_status.error ?? 0)} gagal`} icon="🩺" />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* per tool */}
        <div className="rounded-2xl border border-c surface-2 p-4">
          <div className="mb-3 text-sm font-semibold text-neutral-800 dark:text-neutral-100">
            Pemakaian per Fitur
          </div>
          {data.per_tool.length === 0 ? (
            <div className="py-8 text-center text-xs text-neutral-400">Belum ada data.</div>
          ) : (
            <div className="space-y-2.5">
              {data.per_tool.map((row) => (
                <div key={row.tool} className="flex items-center gap-3">
                  <div className="w-28 shrink-0 truncate text-xs text-neutral-600 dark:text-neutral-300">
                    {toolLabel(row.tool)}
                  </div>
                  <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-neutral-200/60 dark:bg-neutral-800">
                    <div
                      className="h-full rounded-full bg-[color:var(--brand)]"
                      style={{ width: `${(row.count / maxTool) * 100}%` }}
                    />
                  </div>
                  <div className="w-10 shrink-0 text-right text-xs font-medium tabular-nums text-neutral-700 dark:text-neutral-200">
                    {fmtNum(row.count)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* tren harian */}
        <div className="rounded-2xl border border-c surface-2 p-4">
          <div className="mb-3 text-sm font-semibold text-neutral-800 dark:text-neutral-100">
            Tren Harian
          </div>
          {data.daily.length === 0 ? (
            <div className="py-8 text-center text-xs text-neutral-400">Belum ada data.</div>
          ) : (
            <div className="flex h-36 items-end gap-1">
              {data.daily.map((d) => (
                <div
                  key={d.day}
                  className="group relative flex flex-1 flex-col items-center justify-end"
                  title={`${d.day}: ${d.runs} analisis, ${d.users} user`}
                >
                  <div
                    className="w-full rounded-t bg-[color:var(--brand)]/80 transition-all group-hover:bg-[color:var(--brand)]"
                    style={{ height: `${Math.max(4, (d.runs / maxDaily) * 100)}%` }}
                  />
                  <div className="mt-1 text-[9px] text-neutral-400">
                    {d.day.slice(5)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* pengguna teraktif */}
      <div className="rounded-2xl border border-c surface-2 p-4">
        <div className="mb-3 text-sm font-semibold text-neutral-800 dark:text-neutral-100">
          Pengguna Teraktif
        </div>
        {data.top_users.length === 0 ? (
          <div className="py-8 text-center text-xs text-neutral-400">Belum ada aktivitas.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-wider text-neutral-400">
                  <th className="pb-2 pr-3 font-medium">#</th>
                  <th className="pb-2 pr-3 font-medium">Pengguna</th>
                  <th className="pb-2 pr-3 text-right font-medium">Analisis</th>
                </tr>
              </thead>
              <tbody>
                {data.top_users.map((u, i) => (
                  <tr key={u.user_id ?? i} className="border-t border-c">
                    <td className="py-2 pr-3 text-neutral-400">{i + 1}</td>
                    <td className="py-2 pr-3">
                      <div className="font-medium text-neutral-800 dark:text-neutral-100">
                        {u.name || u.email || `User #${u.user_id ?? "?"}`}
                      </div>
                      {u.email && u.name ? (
                        <div className="text-xs text-neutral-400">{u.email}</div>
                      ) : null}
                    </td>
                    <td className="py-2 pr-3 text-right font-semibold tabular-nums text-neutral-700 dark:text-neutral-200">
                      {fmtNum(u.runs)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* feed aktivitas */}
      <div className="rounded-2xl border border-c surface-2 p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div className="text-sm font-semibold text-neutral-800 dark:text-neutral-100">
            Aktivitas Terbaru
          </div>
          <select
            value={toolFilter}
            onChange={(e) => setToolFilter(e.target.value)}
            className="rounded-lg border border-c surface-2 px-2 py-1 text-xs text-neutral-600 dark:text-neutral-300"
          >
            <option value="">Semua fitur</option>
            {data.per_tool.map((r) => (
              <option key={r.tool} value={r.tool}>
                {toolLabel(r.tool)}
              </option>
            ))}
          </select>
        </div>
        {feed.length === 0 ? (
          <div className="py-8 text-center text-xs text-neutral-400">Belum ada aktivitas.</div>
        ) : (
          <ul className="divide-y divide-[color:var(--border)]">
            {feed.map((it) => (
              <li key={it.id} className="flex items-center gap-3 py-2.5">
                <span className="inline-flex shrink-0 items-center rounded-full bg-[color:var(--brand)]/10 px-2 py-0.5 text-[11px] font-medium text-[color:var(--brand)]">
                  {toolLabel(it.tool)}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm text-neutral-700 dark:text-neutral-200">
                    {it.title || it.input_preview || "—"}
                  </div>
                  <div className="truncate text-xs text-neutral-400">
                    {it.name || it.email || `User #${it.user_id ?? "?"}`}
                  </div>
                </div>
                <div className="shrink-0 text-xs text-neutral-400">
                  {timeAgo(it.created_at)}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

/* ------------------------------- USERS ------------------------------- */

function UsersTab({ adminId, isSuper }: { adminId: number; isSuper: boolean }) {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [stats, setStats] = useState<UserStats | null>(null);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<string | null>(null);
  const [historyUser, setHistoryUser] = useState<AdminUser | null>(null);

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
    // eslint-disable-next-line react-hooks/set-state-in-effect -- muat data saat mount (fetch)
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

  async function addTokens(u: AdminUser, amount: number) {
    try {
      const d = await giveTokens(u.id, { add: amount });
      setUsers((prev) =>
        prev.map((x) => (x.id === u.id ? { ...x, token_balance: d.token_balance } : x)),
      );
      setMsg(`✓ +Rp${amount.toLocaleString("id-ID")} saldo untuk ${u.email}`);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Gagal menambah saldo.");
    }
  }

  async function subscribe(u: AdminUser, cancel: boolean) {
    const ask = cancel
      ? `Batalkan langganan ${u.email}?`
      : `Aktifkan/perpanjang langganan ${u.email}? Pastikan pembayaran sudah diterima.`;
    if (!confirm(ask)) return;
    try {
      const d = await setSubscription(u.id, cancel ? { cancel: true } : {});
      setUsers((prev) => prev.map((x) => (x.id === u.id ? { ...x, sub_until: d.sub_until } : x)));
      setMsg(
        cancel
          ? `✓ Langganan ${u.email} dibatalkan`
          : `✓ Langganan ${u.email} aktif s.d. ${fmtDate(d.sub_until)}`,
      );
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Gagal mengubah langganan.");
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
                <th className="px-3 py-3">Saldo (Rp)</th>
                <th className="px-3 py-3">Langganan</th>
                <th className="px-3 py-3">Peran</th>
                <th className="px-3 py-3">Status</th>
                {isSuper && <th className="px-3 py-3">Aksi</th>}
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
                    {u.is_demo ? (
                      <span className="text-xs text-neutral-400">∞ (demo)</span>
                    ) : (
                      <div className="space-y-1.5">
                        {isSuper ? (
                          <TokenEditor
                            value={u.token_balance}
                            onSave={(v) => update(u.id, { token_balance: v }, "Saldo diperbarui")}
                          />
                        ) : (
                          <div className="font-medium">{u.token_balance.toLocaleString("id-ID")}</div>
                        )}
                        {/* Admin biasa hanya boleh menambah ke pengguna biasa. */}
                        {(isSuper || (!u.is_admin && !u.is_staff && u.id !== adminId)) && (
                          <TokenGiver onGive={(n) => addTokens(u, n)} />
                        )}
                      </div>
                    )}
                  </td>
                  <td className="px-3 py-3">
                    {u.is_demo ? (
                      <span className="text-xs text-neutral-400">—</span>
                    ) : (
                      <div className="space-y-1.5">
                        {subActive(u.sub_until) ? (
                          <div className="text-xs font-medium text-emerald-600">
                            Aktif s.d. {fmtDate(u.sub_until)}
                          </div>
                        ) : (
                          <div className="text-xs text-neutral-400">Tidak aktif</div>
                        )}
                        <div className="flex flex-wrap gap-1">
                          <button
                            onClick={() => subscribe(u, false)}
                            className="rounded-lg border border-c surface-2 px-2 py-1 text-xs hover:bg-neutral-50 dark:hover:bg-neutral-900"
                          >
                            {subActive(u.sub_until) ? "+ Perpanjang" : "Aktifkan"}
                          </button>
                          {isSuper && subActive(u.sub_until) && (
                            <button
                              onClick={() => subscribe(u, true)}
                              className="rounded-lg px-2 py-1 text-xs text-red-500 hover:underline"
                            >
                              Batalkan
                            </button>
                          )}
                        </div>
                      </div>
                    )}
                  </td>
                  <td className="px-3 py-3">
                    {isSuper && !u.is_admin && !u.is_demo ? (
                      <button
                        onClick={() =>
                          update(
                            u.id,
                            { is_staff: !u.is_staff },
                            u.is_staff ? "Peran Admin dicabut" : "Dijadikan Admin",
                          )
                        }
                        className={`rounded-full px-3 py-1 text-xs font-medium ${
                          u.is_staff
                            ? "bg-violet-100 text-violet-700 dark:bg-violet-950 dark:text-violet-300"
                            : "bg-neutral-100 text-neutral-500 dark:bg-neutral-800"
                        }`}
                        title="Klik untuk mengubah peran"
                      >
                        {u.is_staff ? "Admin" : "Pengguna"}
                      </button>
                    ) : (
                      <span className="text-xs text-neutral-500">
                        {u.is_admin ? "Super Admin" : u.is_staff ? "Admin" : u.is_demo ? "Demo" : "Pengguna"}
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-3">
                    {!isSuper ? (
                      <span className={`text-xs ${u.is_active ? "text-emerald-600" : "text-red-500"}`}>
                        {u.is_active ? "Aktif" : "Nonaktif"}
                      </span>
                    ) : (
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
                    )}
                  </td>
                  {isSuper && (
                  <td className="px-3 py-3">
                    <div className="flex gap-2">
                      <button
                        onClick={() => setHistoryUser(u)}
                        className="rounded-lg border border-c surface-2 px-2 py-1 text-xs hover:bg-neutral-50 dark:hover:bg-neutral-900"
                      >
                        Riwayat
                      </button>
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
                  )}
                </tr>
              ))}
              {users.length === 0 && (
                <tr>
                  <td colSpan={isSuper ? 6 : 5} className="px-3 py-8 text-center text-neutral-500">
                    Tidak ada pengguna.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
      {historyUser && (
        <HistoryModal user={historyUser} onClose={() => setHistoryUser(null)} />
      )}
    </div>
  );
}

function HistoryModal({ user, onClose }: { user: AdminUser; onClose: () => void }) {
  const [items, setItems] = useState<HistoryItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    userHistory(user.id, 100)
      .then((d) => alive && setItems(d.items))
      .catch((e) => alive && setError(e instanceof Error ? e.message : "Gagal memuat riwayat."));
    return () => {
      alive = false;
    };
  }, [user.id]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        className="max-h-[80vh] w-full max-w-2xl overflow-hidden rounded-2xl border border-c surface shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-c px-5 py-4">
          <div>
            <div className="text-sm font-semibold text-neutral-900 dark:text-neutral-50">
              Riwayat penggunaan
            </div>
            <div className="text-xs text-neutral-500">{user.email || user.name || `#${user.id}`}</div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg border border-c surface-2 px-3 py-1 text-xs hover:bg-neutral-50 dark:hover:bg-neutral-900"
          >
            Tutup
          </button>
        </div>
        <div className="max-h-[60vh] overflow-y-auto px-5 py-3">
          {error ? (
            <div className="py-8 text-center text-sm text-red-600">{error}</div>
          ) : items === null ? (
            <div className="py-8 text-center text-sm text-neutral-500">Memuat…</div>
          ) : items.length === 0 ? (
            <div className="py-8 text-center text-sm text-neutral-500">
              Tidak ada riwayat dalam periode penyimpanan.
            </div>
          ) : (
            <ul className="divide-y divide-[color:var(--border)]">
              {items.map((it) => (
                <li key={it.id} className="py-3">
                  <div className="flex items-center justify-between gap-3">
                    <span className="rounded-full bg-neutral-100 px-2 py-0.5 text-[11px] font-medium text-neutral-600 dark:bg-neutral-800 dark:text-neutral-300">
                      {FEATURE_LABELS[it.tool] || it.tool}
                    </span>
                    <span className="shrink-0 text-xs text-neutral-400">
                      {it.created_at ? new Date(it.created_at).toLocaleString("id-ID") : "-"}
                    </span>
                  </div>
                  {it.title && (
                    <div className="mt-1 text-sm text-neutral-800 dark:text-neutral-100">{it.title}</div>
                  )}
                  {it.input_preview && (
                    <div className="mt-0.5 line-clamp-2 text-xs text-neutral-500">{it.input_preview}</div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

function TokenGiver({ onGive }: { onGive: (n: number) => Promise<void> | void }) {
  const [v, setV] = useState("8000");
  const [busy, setBusy] = useState(false);
  const n = parseInt(v || "0", 10);
  return (
    <div className="flex items-center gap-1">
      <input
        type="number"
        value={v}
        min={1}
        onChange={(e) => setV(e.target.value)}
        className="w-24 rounded-lg border border-c surface-2 px-2 py-1 text-xs outline-none focus:border-[color:var(--brand)]"
        aria-label="Jumlah saldo (Rp) yang ditambahkan"
      />
      <button
        disabled={busy || !(n >= 1)}
        onClick={async () => {
          setBusy(true);
          try {
            await onGive(n);
          } finally {
            setBusy(false);
          }
        }}
        className="rounded-lg border border-c surface-2 px-2 py-1 text-xs hover:bg-neutral-50 disabled:opacity-40 dark:hover:bg-neutral-900"
      >
        + Tambah
      </button>
    </div>
  );
}

const AUDIT_LABELS: Record<string, string> = {
  "tokens.add": "Menambah saldo",
  "subscription.activate": "Mengaktifkan langganan",
  "subscription.cancel": "Membatalkan langganan",
  "tokens.set": "Menetapkan saldo",
  "user.tokens_set": "Menetapkan saldo",
  "user.role": "Mengubah peran Admin",
  "user.active": "Mengubah status aktif",
  "user.rename": "Mengubah nama",
  "user.reset_password": "Reset kata sandi",
  "user.delete": "Menghapus pengguna",
};

function auditDetail(a: AuditItem): string {
  const d = a.detail ?? {};
  if (a.action === "tokens.add")
    return `+${d.add} (saldo ${d.balance_before} → ${d.balance_after})`;
  if (a.action === "tokens.set") return `saldo ${d.balance_before} → ${d.balance_after}`;
  if (a.action === "subscription.activate")
    return `+${d.days} hari, s.d. ${fmtDate(d.sub_until as string | null)}` +
      (d.referral_bonus ? " · bonus referral diberikan" : "");
  if ("from" in d || "to" in d) return `${String(d.from)} → ${String(d.to)}`;
  return "";
}

function AuditTab() {
  const [items, setItems] = useState<AuditItem[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    listAudit(200)
      .then((d) => setItems(d.items))
      .catch((e) => setErr(e instanceof Error ? e.message : "Gagal memuat."));
  }, []);

  if (err) return <div className="p-6 text-sm text-red-500">{err}</div>;
  if (!items) return <div className="p-8 text-center text-sm text-neutral-500">Memuat…</div>;
  return (
    <div className="overflow-x-auto rounded-xl border border-c surface">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-c text-left text-xs uppercase tracking-wide text-neutral-400">
            <th className="px-3 py-3">Waktu</th>
            <th className="px-3 py-3">Oleh</th>
            <th className="px-3 py-3">Tindakan</th>
            <th className="px-3 py-3">Pengguna</th>
            <th className="px-3 py-3">Rincian</th>
          </tr>
        </thead>
        <tbody>
          {items.map((a) => (
            <tr key={a.id} className="border-b border-c last:border-0">
              <td className="whitespace-nowrap px-3 py-2 text-xs text-neutral-500">
                {timeAgo(a.created_at)}
              </td>
              <td className="px-3 py-2 text-xs">
                {a.actor_email}
                <span className="ml-1 rounded bg-neutral-100 px-1 text-[10px] text-neutral-500 dark:bg-neutral-800">
                  {a.actor_role === "super" ? "Super" : "Admin"}
                </span>
              </td>
              <td className="px-3 py-2">{AUDIT_LABELS[a.action] ?? a.action}</td>
              <td className="px-3 py-2 text-xs">{a.target_email ?? "—"}</td>
              <td className="px-3 py-2 text-xs text-neutral-500">{auditDetail(a)}</td>
            </tr>
          ))}
          {items.length === 0 && (
            <tr>
              <td colSpan={5} className="px-3 py-8 text-center text-neutral-500">
                Belum ada tindakan tercatat.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function TokenEditor({ value, onSave }: { value: number; onSave: (v: number) => void }) {
  const [v, setV] = useState(String(value));
  const [lastValue, setLastValue] = useState(value);
  if (lastValue !== value) {
    setLastValue(value);
    setV(String(value));
  }
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
                Saldo Awal Pengguna Baru (Rp)
              </div>
              <div className="text-xs text-neutral-500">
                Saldo gratis untuk setiap pengguna baru (0 = tanpa bonus).
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
          Proteksi Penyalahgunaan
        </h2>
        <p className="mb-4 text-xs text-neutral-500">
          Pagar anti-abuse. Default nonaktif agar tidak mengganggu pengguna. Super
          Admin selalu dikecualikan.
        </p>
        <div className="space-y-4">
          <ToggleRow
            label="Batas Laju (Rate Limit)"
            desc="Batasi jumlah permintaan fitur per menit untuk tiap pengguna/IP."
            checked={s.rate_limit_enabled}
            disabled={saving}
            onChange={(v) => save({ rate_limit_enabled: v })}
          />
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="font-medium text-neutral-900 dark:text-neutral-50">
                Permintaan / Menit
              </div>
              <div className="text-xs text-neutral-500">
                Maksimum permintaan fitur per menit per identitas.
              </div>
            </div>
            <TokenEditor
              value={s.rate_limit_per_min}
              onSave={(v) => save({ rate_limit_per_min: v })}
            />
          </div>
          <ToggleRow
            label="Fitur Berbayar (Potong Saldo)"
            desc="Jika aktif, setiap pemakaian memotong saldo Rupiah pengguna sesuai harga fitur; saldo kurang = ditolak. Gagal = otomatis dikembalikan."
            checked={s.token_enforcement}
            disabled={saving}
            onChange={(v) => save({ token_enforcement: v })}
            danger
          />
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="font-medium text-neutral-900 dark:text-neutral-50">
                Harga Default (Rp)
              </div>
              <div className="text-xs text-neutral-500">
                Dipakai untuk fitur yang belum diberi harga khusus di bawah.
              </div>
            </div>
            <TokenEditor
              value={s.default_tool_cost}
              onSave={(v) => save({ default_tool_cost: v })}
            />
          </div>
        </div>
      </section>

      <PriceSection s={s} saving={saving} save={save} />
      <PaymentSection s={s} saving={saving} save={save} />
      <PackagesSection s={s} saving={saving} save={save} />

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

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("id-ID", { dateStyle: "medium", timeStyle: "short" });
}

function subActive(iso: string | null | undefined): boolean {
  return !!iso && new Date(iso).getTime() > Date.now();
}

type SectionProps = {
  s: AppSettings;
  saving: boolean;
  save: (patch: Partial<AppSettings>) => Promise<void>;
};

const inputCls =
  "rounded-lg border border-c surface-2 px-2 py-1 text-sm outline-none focus:border-[color:var(--brand)]";

function PriceSection({ s, saving, save }: SectionProps) {
  const [draft, setDraft] = useState<Record<string, string>>({});
  const value = (slug: string) =>
    draft[slug] ?? (slug in s.tool_costs ? String(s.tool_costs[slug]) : "");
  const dirty = Object.keys(draft).length > 0;

  function submit() {
    const next: Record<string, number> = { ...s.tool_costs };
    for (const [slug, raw] of Object.entries(draft)) {
      if (raw.trim() === "") delete next[slug];
      else next[slug] = Math.max(0, parseInt(raw, 10) || 0);
    }
    save({ tool_costs: next }).then(() => setDraft({}));
  }

  return (
    <section className="rounded-xl border border-c surface p-5">
      <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-neutral-500">
        Harga per Fitur (Rp)
      </h2>
      <p className="mb-4 text-xs text-neutral-500">
        Kosongkan = pakai harga default (Rp{s.default_tool_cost.toLocaleString("id-ID")}). Isi 0 =
        gratis. AI Chat &amp; Doc Chat dihitung per pesan. &quot;Ekstrak Teks&quot; dan &quot;Laporan
        PDF&quot; sebaiknya 0 agar pengguna tidak terpotong dua kali.
      </p>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {s.priced_slugs.map((slug) => (
          <label
            key={slug}
            className="flex items-center justify-between gap-2 rounded-lg border border-c surface-2 px-3 py-2 text-sm"
          >
            <span>{FEATURE_LABELS[slug] ?? slug}</span>
            <input
              type="number"
              min={0}
              value={value(slug)}
              placeholder={String(s.default_tool_cost)}
              onChange={(e) => setDraft((d) => ({ ...d, [slug]: e.target.value }))}
              className={inputCls + " w-24 text-right"}
            />
          </label>
        ))}
      </div>
      {dirty && (
        <div className="mt-3 flex gap-2">
          <button
            disabled={saving}
            onClick={submit}
            className="rounded-lg bg-[color:var(--brand)] px-3 py-1.5 text-sm text-white disabled:opacity-50"
          >
            Simpan Harga
          </button>
          <button onClick={() => setDraft({})} className="rounded-lg px-3 py-1.5 text-sm text-neutral-500">
            Batal
          </button>
        </div>
      )}
    </section>
  );
}

const PAYMENT_FIELDS: { key: keyof PaymentInfo; label: string; hint: string }[] = [
  { key: "dana_number", label: "Nomor DANA", hint: "contoh 081234567890" },
  { key: "dana_name", label: "Nama pemilik DANA", hint: "nama yang muncul saat transfer" },
  { key: "wa_primary", label: "WhatsApp utama", hint: "nomor penerima bukti transfer" },
  { key: "wa_backup", label: "WhatsApp cadangan", hint: "kosongkan bila belum ada" },
  { key: "backup_delay_sec", label: "Tampilkan cadangan setelah (detik)", hint: "default 60" },
  { key: "note", label: "Catatan untuk pengguna", hint: "mis. jam layanan" },
];

function PaymentSection({ s, saving, save }: SectionProps) {
  const [form, setForm] = useState<PaymentInfo>(s.payment_info);
  const [base, setBase] = useState(s.payment_info);
  if (base !== s.payment_info) {
    setBase(s.payment_info);
    setForm(s.payment_info);
  }
  const dirty = JSON.stringify(form) !== JSON.stringify(s.payment_info);
  return (
    <section className="rounded-xl border border-c surface p-5">
      <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-neutral-500">
        Info Pembayaran (DANA &amp; WhatsApp)
      </h2>
      <p className="mb-4 text-xs text-neutral-500">
        Ditampilkan di halaman Isi Saldo. Selama nomor DANA/WA kosong, pengguna melihat pesan
        &quot;info pembayaran belum tersedia&quot;.
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        {PAYMENT_FIELDS.map((f) => (
          <label key={f.key} className="text-sm">
            <div className="mb-1 font-medium">{f.label}</div>
            <input
              type={f.key === "backup_delay_sec" ? "number" : "text"}
              value={String(form[f.key] ?? "")}
              placeholder={f.hint}
              onChange={(e) =>
                setForm((p) => ({
                  ...p,
                  [f.key]:
                    f.key === "backup_delay_sec" ? parseInt(e.target.value || "0", 10) : e.target.value,
                }))
              }
              className={inputCls + " w-full"}
            />
          </label>
        ))}
      </div>
      {dirty && (
        <button
          disabled={saving}
          onClick={() => save({ payment_info: form })}
          className="mt-3 rounded-lg bg-[color:var(--brand)] px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          Simpan Info Pembayaran
        </button>
      )}
    </section>
  );
}

const PACKAGE_FIELDS: { key: Exclude<keyof Packages, "revision_tools">; label: string; step?: number }[] = [
  { key: "subscription_price", label: "Harga langganan (Rp)" },
  { key: "subscription_days", label: "Durasi langganan (hari)" },
  { key: "revision_discount_pct", label: "Diskon cek ulang revisi (%)" },
  { key: "revision_window_hours", label: "Batas waktu cek ulang (jam)" },
  { key: "revision_max", label: "Maks. cek ulang berdiskon per dokumen" },
  { key: "revision_min_similarity", label: "Kemiripan minimal dokumen revisi (0–1)", step: 0.05 },
  { key: "referral_bonus", label: "Bonus referral tiap pihak (Rp)" },
  { key: "referral_min_topup", label: "Min. isi saldo teman agar bonus cair (Rp)" },
];

function PackagesSection({ s, saving, save }: SectionProps) {
  const [form, setForm] = useState<Packages>(s.packages);
  const [base, setBase] = useState(s.packages);
  if (base !== s.packages) {
    setBase(s.packages);
    setForm(s.packages);
  }
  const dirty = JSON.stringify(form) !== JSON.stringify(s.packages);
  return (
    <section className="rounded-xl border border-c surface p-5">
      <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-neutral-500">
        Paket: Langganan, Diskon Revisi, Referral
      </h2>
      <p className="mb-4 text-xs text-neutral-500">
        Diskon revisi berlaku untuk: {s.packages.revision_tools.map((t) => FEATURE_LABELS[t] ?? t).join(", ")}.
        Isi diskon 0 atau bonus 0 untuk mematikan paket terkait.
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        {PACKAGE_FIELDS.map((f) => (
          <label key={f.key} className="text-sm">
            <div className="mb-1 font-medium">{f.label}</div>
            <input
              type="number"
              min={0}
              step={f.step ?? 1}
              value={String(form[f.key])}
              onChange={(e) => setForm((p) => ({ ...p, [f.key]: Number(e.target.value || 0) }))}
              className={inputCls + " w-full"}
            />
          </label>
        ))}
      </div>
      {dirty && (
        <button
          disabled={saving}
          onClick={() => save({ packages: form })}
          className="mt-3 rounded-lg bg-[color:var(--brand)] px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          Simpan Paket
        </button>
      )}
    </section>
  );
}
