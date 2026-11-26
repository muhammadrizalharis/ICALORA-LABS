"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { costFor, costUnit, formatRp, isUnmetered } from "@/lib/pricing";

/** Info biaya sebelum memakai fitur: harga, saldo, dan ajakan isi saldo bila kurang. */
export default function ToolCostBar({ slug }: { slug: string }) {
  const { user, toolCosts, tokenEnforcement, billing, packages } = useAuth();
  const cost = costFor(slug, toolCosts);
  if (!user || cost === null || !tokenEnforcement) return null;

  if (cost === 0)
    return (
      <div className="mb-4 rounded-xl border border-c surface-2 px-4 py-2 text-sm">
        Fitur ini <b>gratis</b>.
      </div>
    );

  const price = (
    <>
      Biaya <b>{formatRp(cost)}</b> {costUnit(slug)}
    </>
  );

  if (isUnmetered(user))
    return (
      <div className="mb-4 rounded-xl border border-c surface-2 px-4 py-2 text-sm text-neutral-500">
        {price} · akun Anda tidak dipotong saldo.
      </div>
    );

  if (billing?.sub_active)
    return (
      <div className="mb-4 rounded-xl border border-emerald-300 bg-emerald-50 px-4 py-2 text-sm text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-200">
        Langganan aktif · fitur ini <b>bebas pakai</b> tanpa memotong saldo.
      </div>
    );

  const enough = user.token_balance >= cost;
  const hasRevision =
    !!packages && packages.revision_tools.includes(slug) && packages.revision_discount_pct > 0;
  const revisionPrice = hasRevision
    ? cost - Math.floor((cost * packages!.revision_discount_pct) / 100)
    : cost;
  const revision = hasRevision
    ? ` Cek ulang revisi dokumen yang sama dalam ${packages!.revision_window_hours} jam cukup ${formatRp(revisionPrice)}.`
    : "";
  const revisionOnly = !enough && hasRevision && user.token_balance >= revisionPrice;

  return (
    <div
      className={
        "mb-4 flex flex-wrap items-center gap-x-3 gap-y-2 rounded-xl border px-4 py-2 text-sm " +
        (enough
          ? "border-c surface-2"
          : "border-red-300 bg-red-50 text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200")
      }
    >
      <span>
        {price} · Saldo Anda <b>{formatRp(user.token_balance)}</b>
        {enough ? (
          <span className="text-neutral-400">{revision}</span>
        ) : revisionOnly ? (
          <>
            {" "}
            · saldo kurang untuk pemeriksaan baru, tapi cukup untuk cek ulang revisi (
            {formatRp(revisionPrice)}) bila Anda sudah memeriksa dokumen ini dalam{" "}
            {packages!.revision_window_hours} jam terakhir.
          </>
        ) : (
          <> · saldo tidak cukup.</>
        )}
      </span>
      <Link
        href="/dashboard/isi-saldo"
        className={
          "ml-auto rounded-lg px-3 py-1 text-xs font-semibold " +
          (enough
            ? "border border-c hover:bg-neutral-100 dark:hover:bg-neutral-900"
            : "bg-[color:var(--brand)] text-white hover:opacity-90")
        }
      >
        Isi Saldo
      </Link>
    </div>
  );
}
