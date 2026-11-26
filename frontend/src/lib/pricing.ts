import type { User } from "@/lib/auth";

/** Slug halaman frontend → slug biaya di backend (bila berbeda). */
const BACKEND_SLUG: Record<string, string> = {
  "chat-pdf": "doc-chat",
  "transkrip-audio": "transcribe",
  "publikasi-jurnal": "publikasi",
};

const PER_MESSAGE = new Set(["ai-chat", "chat-pdf"]);

export function formatRp(n: number): string {
  return "Rp" + Math.max(0, Math.round(n)).toLocaleString("id-ID");
}

export function costFor(slug: string, toolCosts: Record<string, number>): number | null {
  const key = BACKEND_SLUG[slug] ?? slug;
  return typeof toolCosts[key] === "number" ? toolCosts[key] : null;
}

export function costUnit(slug: string): string {
  return PER_MESSAGE.has(slug) ? "per pesan" : "per pemakaian";
}

/** Akun yang tidak pernah dipotong saldo (Super Admin & demo). */
export function isUnmetered(user: User | null): boolean {
  return Boolean(user?.is_admin || user?.is_demo);
}

/** Normalisasi nomor WA Indonesia ke format wa.me (62…). */
export function waLink(number: string, message: string): string | null {
  let digits = (number || "").replace(/\D/g, "");
  if (!digits) return null;
  if (digits.startsWith("0")) digits = "62" + digits.slice(1);
  else if (digits.startsWith("8")) digits = "62" + digits;
  if (digits.length < 9) return null;
  return `https://wa.me/${digits}?text=${encodeURIComponent(message)}`;
}
