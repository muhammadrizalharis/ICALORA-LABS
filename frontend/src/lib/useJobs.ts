"use client";

import { useCallback } from "react";
import { useSyncExternalStore } from "react";
import { useRouter } from "next/navigation";
import {
  subscribe,
  getJobsSnapshot,
  getHistoryVersion,
  startJob,
  type Job,
  type StartJobOptions,
} from "@/lib/jobs";

export function useJobs(): Job[] {
  return useSyncExternalStore(subscribe, getJobsSnapshot, getJobsSnapshot);
}

export function useHistoryVersion(): number {
  return useSyncExternalStore(subscribe, getHistoryVersion, getHistoryVersion);
}

// Memulai pekerjaan lalu langsung mengarahkan pengguna ke Beranda, tempat
// status proses (sedang diproses / selesai / gagal) ditampilkan.
export function useJobLauncher(): (opts: StartJobOptions) => void {
  const router = useRouter();
  return useCallback(
    (opts: StartJobOptions) => {
      startJob(opts);
      router.push("/dashboard");
    },
    [router],
  );
}
