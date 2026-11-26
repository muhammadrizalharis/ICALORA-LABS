"use client";

import { useEffect, useMemo, useState } from "react";
import { useAuth } from "@/lib/auth";
import { FEATURES } from "@/lib/features";
import { costFor, costUnit, formatRp, isUnmetered, waLink } from "@/lib/pricing";

const AMOUNTS = [8_000, 15_000, 25_000, 50_000, 100_000];
const SUB = "langganan";

function CopyButton({ value }: { value: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      onClick={() => {
        navigator.clipboard?.writeText(value).then(() => {
          setDone(true);
          setTimeout(() => setDone(false), 1500);
        });
      }}
      className="rounded-md border border-c px-2 py-1 text-xs hover:bg-neutral-100 dark:hover:bg-neutral-900"
    >
      {done ? "Tersalin ✓" : "Salin"}
    </button>
  );
}

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString("id-ID", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

export default function IsiSaldoPage() {
  const { user, toolCosts, paymentInfo, packages, billing, refresh } = useAuth();
  const [choice, setChoice] = useState<number | typeof SUB>(AMOUNTS[0]);
  const [waClickedAt, setWaClickedAt] = useState<number | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [origin, setOrigin] = useState("");

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/set-state-in-effect -- origin hanya ada di browser
    setOrigin(window.location.origin);
  }, [refresh]);

  useEffect(() => {
    if (waClickedAt === null) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [waClickedAt]);

  const subPrice = packages?.subscription_price ?? 0;
  const subDays = packages?.subscription_days ?? 30;
  const amountLabel =
    choice === SUB ? `Langganan ${subDays} hari (${formatRp(subPrice)})` : formatRp(choice);
  const message =
    `Halo admin ICALORA, saya sudah transfer untuk ${choice === SUB ? "aktivasi" : "isi saldo"} ` +
    `${amountLabel}.\nEmail akun: ${user?.email ?? "-"}\nBukti transfer saya lampirkan.`;

  const pi = paymentInfo;
  const primary = pi ? waLink(pi.wa_primary, message) : null;
  const backup = pi ? waLink(pi.wa_backup, message) : null;
  const delay = pi?.backup_delay_sec ?? 60;
  const remaining =
    waClickedAt === null ? delay : Math.max(0, delay - Math.floor((now - waClickedAt) / 1000));
  const showBackup = Boolean(backup) && waClickedAt !== null && remaining === 0;

  const priceRows = useMemo(
    () =>
      FEATURES.filter((f) => f.status === "active")
        .map((f) => ({ f, cost: costFor(f.slug, toolCosts) }))
        .filter((r) => r.cost !== null)
        .sort((a, b) => (b.cost ?? 0) - (a.cost ?? 0)),
    [toolCosts],
  );

  const refLink =
    billing?.referral_code && origin ? `${origin}/login?ref=${billing.referral_code}` : "";
  const unmetered = isUnmetered(user);
  const chip = (active: boolean) =>
    "rounded-lg border px-3 py-1.5 text-sm " +
    (active
      ? "border-[color:var(--brand)] bg-[color:var(--brand-soft)] font-semibold text-[color:var(--brand)]"
      : "border-c hover:bg-neutral-100 dark:hover:bg-neutral-900");

  return (
    <div className="mx-auto max-w-4xl p-8">
      <div className="text-[11px] uppercase tracking-wide text-neutral-400">Akun</div>
      <h1 className="text-2xl font-bold text-neutral-900 dark:text-neutral-50">Isi Saldo & Harga</h1>
      <p className="mt-1 text-sm text-neutral-500 dark:text-neutral-400">
        Setiap fitur memotong saldo sesuai harga di bawah. Isi saldo lewat transfer DANA, lalu kirim
        bukti transfer ke WhatsApp admin. Saldo masuk setelah admin mengonfirmasi.
      </p>

      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        <div className="rounded-2xl border border-c surface-2 p-5">
          <div className="text-xs text-neutral-500">Saldo Anda</div>
          <div className="mt-1 text-2xl font-bold">
            {unmetered ? "∞" : formatRp(user?.token_balance ?? 0)}
          </div>
          {unmetered && (
            <div className="text-xs text-neutral-400">Akun ini tidak dipotong saldo</div>
          )}
        </div>
        <div className="rounded-2xl border border-c surface-2 p-5">
          <div className="text-xs text-neutral-500">Langganan</div>
          {billing?.sub_active && billing.sub_until ? (
            <>
              <div className="mt-1 text-2xl font-bold text-emerald-600">Aktif</div>
              <div className="text-xs text-neutral-400">
                Bebas pakai semua fitur s.d. {fmtDate(billing.sub_until)}
              </div>
            </>
          ) : (
            <>
              <div className="mt-1 text-2xl font-bold text-neutral-400">Tidak aktif</div>
              <div className="text-xs text-neutral-400">Pemakaian memotong saldo</div>
            </>
          )}
        </div>
      </div>

      <section className="mt-8 rounded-2xl border border-c surface p-6">
        <h2 className="text-lg font-semibold">Cara isi saldo</h2>

        <div className="mt-4 text-sm font-medium">1. Pilih nominal</div>
        <div className="mt-2 flex flex-wrap gap-2">
          {AMOUNTS.map((a) => (
            <button key={a} type="button" onClick={() => setChoice(a)} className={chip(choice === a)}>
              {formatRp(a)}
            </button>
          ))}
          {subPrice > 0 && (
            <button type="button" onClick={() => setChoice(SUB)} className={chip(choice === SUB)}>
              Langganan {formatRp(subPrice)}
            </button>
          )}
        </div>
        <p className="mt-1 text-xs text-neutral-400">
          Nominal lain juga boleh. Sebutkan saja di pesan WhatsApp.
        </p>

        <div className="mt-5 text-sm font-medium">2. Transfer ke DANA</div>
        {pi?.dana_number ? (
          <div className="mt-2 flex flex-wrap items-center gap-3 rounded-xl border border-c surface-2 p-4">
            <div>
              <div className="font-mono text-lg font-bold tracking-wide">{pi.dana_number}</div>
              {pi.dana_name && <div className="text-xs text-neutral-500">a.n. {pi.dana_name}</div>}
            </div>
            <CopyButton value={pi.dana_number.replace(/\s/g, "")} />
            <div className="ml-auto text-sm">
              Jumlah: <b>{choice === SUB ? formatRp(subPrice) : formatRp(choice)}</b>
            </div>
          </div>
        ) : (
          <div className="mt-2 rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200">
            Nomor pembayaran belum diatur admin. Silakan coba lagi nanti.
          </div>
        )}

        <div className="mt-5 text-sm font-medium">3. Kirim bukti transfer lewat WhatsApp</div>
        {primary ? (
          <div className="mt-2 space-y-2">
            <a
              href={primary}
              target="_blank"
              rel="noopener noreferrer"
              onClick={() => {
                setWaClickedAt(Date.now());
                setNow(Date.now());
              }}
              className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700"
            >
              💬 Kirim bukti ke WhatsApp Admin
            </a>
            {backup && waClickedAt !== null && !showBackup && (
              <div className="text-xs text-neutral-400">
                Jika admin belum membalas dalam {remaining} detik, tombol admin cadangan akan muncul.
              </div>
            )}
            {showBackup && backup && (
              <div className="rounded-xl border border-c surface-2 p-3 text-sm">
                Belum dibalas?{" "}
                <a
                  href={backup}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-semibold text-emerald-600 underline"
                >
                  Hubungi admin cadangan
                </a>
              </div>
            )}
          </div>
        ) : (
          <div className="mt-2 text-sm text-neutral-500">Nomor WhatsApp admin belum diatur.</div>
        )}

        <div className="mt-5 text-sm font-medium">4. Saldo masuk</div>
        <p className="mt-1 text-sm text-neutral-500">
          Setelah admin mengonfirmasi, saldo atau langganan langsung aktif di akun{" "}
          <b>{user?.email}</b>. Muat ulang halaman ini untuk melihatnya.
        </p>
        {pi?.note && <p className="mt-3 text-xs text-neutral-500">{pi.note}</p>}
      </section>

      {packages && (
        <section className="mt-8 grid gap-4 md:grid-cols-3">
          <div className="rounded-2xl border border-c surface p-5">
            <div className="text-2xl">♾️</div>
            <h3 className="mt-1 font-semibold">Langganan Bulanan</h3>
            <div className="mt-1 text-xl font-bold">{formatRp(packages.subscription_price)}</div>
            <p className="mt-1 text-xs text-neutral-500">
              Bebas pakai semua fitur selama {packages.subscription_days} hari tanpa memotong saldo.
              Cocok untuk masa revisi skripsi.
            </p>
          </div>
          {packages.revision_max > 0 && packages.revision_discount_pct > 0 && (
            <div className="rounded-2xl border border-c surface p-5">
              <div className="text-2xl">🔁</div>
              <h3 className="mt-1 font-semibold">Diskon Cek Ulang Revisi</h3>
              <div className="mt-1 text-xl font-bold">
                {packages.revision_discount_pct}% lebih murah
              </div>
              <p className="mt-1 text-xs text-neutral-500">
                Setelah cek Plagiarism atau AI Detector harga penuh, cek ulang dokumen yang sama
                (sudah direvisi) dalam {packages.revision_window_hours} jam otomatis mendapat diskon
                {packages.revision_max > 1 ? ` (maks. ${packages.revision_max}×)` : " (1×)"}.
                Sistem mengenali dokumen dari kemiripan isinya.
              </p>
            </div>
          )}
          {packages.referral_bonus > 0 && (
            <div className="rounded-2xl border border-c surface p-5">
              <div className="text-2xl">🤝</div>
              <h3 className="mt-1 font-semibold">Ajak Teman</h3>
              <div className="mt-1 text-xl font-bold">
                {formatRp(packages.referral_bonus)} untuk berdua
              </div>
              <p className="mt-1 text-xs text-neutral-500">
                Teman mendaftar lewat link Anda. Saat ia pertama kali isi saldo minimal{" "}
                {formatRp(packages.referral_min_topup)}, Anda dan teman masing-masing mendapat{" "}
                {formatRp(packages.referral_bonus)}.
              </p>
              {refLink && (
                <div className="mt-3 space-y-1">
                  <div className="flex items-center gap-2">
                    <code className="truncate rounded bg-neutral-100 px-2 py-1 text-[11px] dark:bg-neutral-900">
                      {refLink}
                    </code>
                    <CopyButton value={refLink} />
                  </div>
                  <div className="text-[11px] text-neutral-400">
                    {billing?.referral.joined ?? 0} teman mendaftar ·{" "}
                    {billing?.referral.rewarded ?? 0} bonus cair
                  </div>
                </div>
              )}
            </div>
          )}
        </section>
      )}

      <section className="mt-8 rounded-2xl border border-c surface p-6">
        <h2 className="text-lg font-semibold">Daftar harga</h2>
        <table className="mt-3 w-full text-sm">
          <tbody>
            {priceRows.map(({ f, cost }) => (
              <tr key={f.slug} className="border-t border-c">
                <td className="py-2">
                  <span className="mr-2">{f.icon}</span>
                  {f.name}
                </td>
                <td className="py-2 text-right font-semibold">
                  {cost ? formatRp(cost) : "Gratis"}
                  {cost ? (
                    <span className="ml-1 text-xs font-normal text-neutral-400">
                      {costUnit(f.slug)}
                    </span>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-3 text-xs text-neutral-400">
          Jika pemeriksaan gagal karena kesalahan server, saldo dikembalikan otomatis.
        </p>
      </section>
    </div>
  );
}
