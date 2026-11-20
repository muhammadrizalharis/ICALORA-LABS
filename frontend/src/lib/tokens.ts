import type { User } from "@/lib/auth";

export interface TokenView {
  value: string;
  note: string;
  low: boolean;
}

/** Tampilan saldo token yang jujur: saldo nyata, kecuali akun yang memang tanpa potongan. */
export function tokenView(
  user: User | null,
  enforcement: boolean,
  toolCost: number,
): TokenView {
  if (!user) return { value: "—", note: "", low: false };
  if (user.is_admin)
    return { value: "∞", note: "Super Admin · tanpa potongan token", low: false };
  if (user.is_demo)
    return { value: "∞", note: "Akun demo · token tidak terbatas", low: false };
  const value = user.token_balance.toLocaleString("id-ID");
  if (!enforcement)
    return { value, note: "Pemotongan token sedang nonaktif", low: false };
  if (user.token_balance <= 0)
    return {
      value,
      note: "Saldo habis · hubungi admin untuk menambah token",
      low: true,
    };
  return { value, note: `Biasanya ${toolCost} token per analisis`, low: false };
}
