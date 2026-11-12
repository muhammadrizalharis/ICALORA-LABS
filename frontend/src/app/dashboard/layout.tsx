"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import DashboardSidebar from "@/components/DashboardSidebar";
import ThemeToggle from "@/components/ThemeToggle";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { loading, user, maintenanceMode } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-neutral-400">
        Memuat…
      </div>
    );
  }
  if (!user) return null;

  const showMaintenance = maintenanceMode && !user.is_admin;

  return (
    <div className="flex min-h-screen">
      <DashboardSidebar />
      <div className="relative flex-1 overflow-x-hidden">
        <div className="pointer-events-none absolute right-4 top-4 z-20">
          <div className="pointer-events-auto">
            <ThemeToggle />
          </div>
        </div>
        {showMaintenance && (
          <div className="border-b border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-300">
            <b>Mode pemeliharaan aktif.</b> Sebagian fitur untuk sementara tidak
            dapat digunakan. Silakan coba lagi nanti.
          </div>
        )}
        {children}
      </div>
    </div>
  );
}
