"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { FEATURES } from "@/lib/features";
import { useAuth } from "@/lib/auth";
import ThemeToggle from "@/components/ThemeToggle";

const activeFeatures = FEATURES.filter((f) => f.status === "active");

function NavLink({ href, label, icon, active }: { href: string; label: string; icon: string; active: boolean }) {
  return (
    <Link
      href={href}
      className={
        "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition " +
        (active
          ? "bg-[color:var(--brand-soft)] font-medium text-[color:var(--brand)]"
          : "text-neutral-600 hover:bg-neutral-100 dark:text-neutral-400 dark:hover:bg-neutral-900")
      }
    >
      <span className="w-5 text-center">{icon}</span>
      {label}
    </Link>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="px-3 pb-1 pt-4 text-[10px] font-semibold uppercase tracking-wider text-neutral-400">
      {children}
    </div>
  );
}

export default function DashboardSidebar() {
  const pathname = usePathname() || "";
  const { user, logout } = useAuth();

  return (
    <aside className="flex h-screen w-64 shrink-0 flex-col border-r border-c surface">
      <div className="flex items-center gap-2 px-4 py-4">
        <Image src="/Logo Teknologi Futuristik ICALORA-LABS.png" alt="" width={28} height={28} />
        <span className="font-bold tracking-tight">ICALORA-LABS</span>
      </div>

      <nav className="flex-1 overflow-y-auto px-2 pb-4">
        <SectionLabel>Beranda</SectionLabel>
        <NavLink href="/dashboard" label="Beranda" icon="🏠" active={pathname === "/dashboard"} />

        <SectionLabel>Tools</SectionLabel>
        {activeFeatures.map((f) => (
          <NavLink
            key={f.slug}
            href={`/dashboard/tools/${f.slug}`}
            label={f.name}
            icon={f.icon}
            active={pathname === `/dashboard/tools/${f.slug}`}
          />
        ))}

        <SectionLabel>Riwayat</SectionLabel>
        <NavLink href="/dashboard/history" label="Semua Riwayat" icon="🕘" active={pathname.startsWith("/dashboard/history")} />

        <SectionLabel>Akun</SectionLabel>
        <NavLink href="/dashboard/akun" label="Profil & Saldo" icon="👤" active={pathname === "/dashboard/akun"} />
      </nav>

      <div className="border-t border-c p-3">
        <div className="mb-2 flex items-center justify-between">
          <span className="truncate text-xs text-neutral-500 dark:text-neutral-400">
            {user?.name ?? user?.email ?? "Tamu"}
          </span>
          <ThemeToggle />
        </div>
        <button
          onClick={logout}
          className="w-full rounded-lg border border-c px-3 py-2 text-xs text-neutral-600 hover:bg-neutral-100 dark:text-neutral-400 dark:hover:bg-neutral-900"
        >
          Keluar
        </button>
      </div>
    </aside>
  );
}
