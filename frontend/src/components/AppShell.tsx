"use client";

import { usePathname } from "next/navigation";
import TopNav from "@/components/TopNav";
import Footer from "@/components/Footer";

// Sembunyikan navbar/footer publik di area aplikasi (dashboard & login).
const BARE_PREFIXES = ["/dashboard", "/login", "/admin-000"];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() || "/";
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
