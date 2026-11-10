"use client";

import { useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { FEATURES } from "@/lib/features";
import { useAuth } from "@/lib/auth";

const activeFeatures = FEATURES.filter((f) => f.status === "active");

const COLLAPSE_KEY = "icalora_sidebar_collapsed";

function NavLink({
  href,
  label,
  icon,
  active,
  collapsed,
}: {
  href: string;
  label: string;
  icon: string;
  active: boolean;
  collapsed: boolean;
}) {
  return (
    <Link
      href={href}
      title={collapsed ? label : undefined}
      className={
        "flex items-center rounded-lg text-sm transition " +
        (collapsed ? "justify-center px-0 py-2.5" : "gap-3 px-3 py-2") +
        " " +
        (active
          ? "bg-[color:var(--brand-soft)] font-medium text-[color:var(--brand)]"
          : "text-neutral-600 hover:bg-neutral-100 dark:text-neutral-400 dark:hover:bg-neutral-900")
      }
    >
      <span className="w-5 shrink-0 text-center">{icon}</span>
      {!collapsed && <span className="truncate">{label}</span>}
    </Link>
  );
}

function SectionLabel({ children, collapsed }: { children: React.ReactNode; collapsed: boolean }) {
  if (collapsed) return <div className="mx-auto my-2 h-px w-6 bg-neutral-200 dark:bg-neutral-800" />;
  return (
    <div className="px-3 pb-1 pt-4 text-[10px] font-semibold uppercase tracking-wider text-neutral-400">
      {children}
    </div>
  );
}

export default function DashboardSidebar() {
  const pathname = usePathname() || "";
  const { user, logout } = useAuth();
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    try {
      return localStorage.getItem(COLLAPSE_KEY) === "1";
    } catch {
      return false;
    }
  });

  function toggle() {
    setCollapsed((c) => {
      const next = !c;
      try {
        localStorage.setItem(COLLAPSE_KEY, next ? "1" : "0");
      } catch {
        /* abaikan */
      }
      return next;
    });
  }

  return (
    <aside
      className={
        "sticky top-0 flex h-screen shrink-0 flex-col self-start border-r border-c surface transition-[width] duration-200 " +
        (collapsed ? "w-16" : "w-64")
      }
    >
      <div className={"flex items-center py-4 " + (collapsed ? "justify-center px-0" : "gap-2 px-4")}>
        <Image src="/icon.png" alt="" width={28} height={28} className="shrink-0" />
        {!collapsed && <span className="font-bold tracking-tight">ICALORA-LABS</span>}
      </div>

      <div className="px-2 pb-1">
        <button
          onClick={toggle}
          title={collapsed ? "Perluas sidebar" : "Perkecil sidebar"}
          aria-label={collapsed ? "Perluas sidebar" : "Perkecil sidebar"}
          className={
            "flex w-full items-center rounded-lg text-xs text-neutral-500 transition hover:bg-neutral-100 dark:text-neutral-400 dark:hover:bg-neutral-900 " +
            (collapsed ? "justify-center py-2" : "gap-2 px-3 py-2")
          }
        >
          <span className="w-5 shrink-0 text-center text-base">{collapsed ? "»" : "«"}</span>
          {!collapsed && <span>Perkecil</span>}
        </button>
      </div>

      <nav className="thin-scrollbar min-h-0 flex-1 overflow-y-auto px-2 pb-4">
        <SectionLabel collapsed={collapsed}>Beranda</SectionLabel>
        <NavLink
          href="/dashboard"
          label="Beranda"
          icon="🏠"
          active={pathname === "/dashboard"}
          collapsed={collapsed}
        />

        <SectionLabel collapsed={collapsed}>Tools</SectionLabel>
        {activeFeatures.map((f) => (
          <NavLink
            key={f.slug}
            href={`/dashboard/tools/${f.slug}`}
            label={f.name}
            icon={f.icon}
            active={pathname === `/dashboard/tools/${f.slug}`}
            collapsed={collapsed}
          />
        ))}

        <SectionLabel collapsed={collapsed}>Riwayat</SectionLabel>
        <NavLink
          href="/dashboard/history"
          label="Semua Riwayat"
          icon="🕘"
          active={pathname.startsWith("/dashboard/history")}
          collapsed={collapsed}
        />

        <SectionLabel collapsed={collapsed}>Akun</SectionLabel>
        <NavLink
          href="/dashboard/akun"
          label="Profil & Saldo"
          icon="👤"
          active={pathname === "/dashboard/akun"}
          collapsed={collapsed}
        />
      </nav>

      <div className="border-t border-c p-3">
        {!collapsed && (
          <div className="mb-2 truncate text-xs text-neutral-500 dark:text-neutral-400">
            {user?.name ?? user?.email ?? "Tamu"}
          </div>
        )}
        <button
          onClick={logout}
          title="Keluar"
          className={
            "flex w-full items-center justify-center rounded-lg border border-c px-3 py-2 text-xs text-neutral-600 hover:bg-neutral-100 dark:text-neutral-400 dark:hover:bg-neutral-900"
          }
        >
          {collapsed ? "⎋" : "Keluar"}
        </button>
      </div>
    </aside>
  );
}
