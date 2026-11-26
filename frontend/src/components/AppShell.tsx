"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import TopNav from "@/components/TopNav";
import Footer from "@/components/Footer";

// Sembunyikan navbar/footer publik di area aplikasi (dashboard & login).
const BARE_PREFIXES = ["/dashboard", "/login", "/admin=-000"];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() || "/";
  useEffect(() => {
    // Tautan ajak teman: ?ref=KODE disimpan 30 hari, dipakai saat daftar via Google.
    const ref = new URLSearchParams(window.location.search).get("ref");
    if (ref && /^[A-Za-z0-9]{4,16}$/.test(ref))
      document.cookie = `icalora_ref=${ref.toUpperCase()}; max-age=${30 * 86400}; path=/; samesite=lax`;
  }, [pathname]);

  const bare = BARE_PREFIXES.some((p) => pathname === p || pathname.startsWith(p + "/"));

  if (bare) return <>{children}</>;

  return (
    <>
      <TopNav />
      <main className="min-h-[calc(100vh-8rem)]">{children}</main>
      <Footer />
    </>
  );
}
