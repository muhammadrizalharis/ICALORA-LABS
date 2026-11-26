import type { Billing, User } from "@/lib/auth";
import { formatRp } from "@/lib/pricing";

export interface TokenView {
  value: string;
  note: string;
  low: boolean;
}

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString("id-ID", { day: "numeric", month: "long", year: "numeric" });
}

/** Tampilan saldo (Rupiah) yang jujur: saldo nyata, kecuali akun yang memang tanpa potongan. */
export function tokenView(
  user: User | null,
  enforcement: boolean,
  _toolCost: number,
  billing?: Billing | null,
): TokenView {
  if (!user) return { value: "—", note: "", low: false };
  if (user.is_admin)
    return { value: "∞", note: "Super Admin · tanpa potongan saldo", low: false };
  if (user.is_demo)
    return { value: "∞", note: "Akun demo · saldo tidak terbatas", low: false };
  const value = formatRp(user.token_balance);
  if (billing?.sub_active && billing.sub_until)
    return { value, note: `Langganan aktif s.d. ${fmtDate(billing.sub_until)} · bebas pakai`, low: false };
  if (!enforcement)
    return { value, note: "Pemotongan saldo sedang nonaktif", low: false };
  if (user.token_balance <= 0)
    return { value, note: "Saldo habis · isi saldo lewat menu Isi Saldo", low: true };
  return { value, note: "Saldo dipotong sesuai harga tiap fitur", low: false };
}
