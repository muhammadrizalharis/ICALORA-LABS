"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth";

const TOOL_HREF = "/dashboard/tools/plagiarism-checker";

/** Tombol "Periksa Sekarang": ke alat bila sudah masuk, ke halaman masuk bila belum. */
export default function CheckNowLink({
  className,
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  const { user } = useAuth();
  return (
    <Link href={user ? TOOL_HREF : "/login"} className={className}>
      {children}
    </Link>
  );
}
