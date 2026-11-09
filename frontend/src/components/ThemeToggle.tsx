"use client";

import { useEffect, useState } from "react";

type Theme = "light" | "dark" | "system";

const STORAGE_KEY = "theme";
const CYCLE: Theme[] = ["light", "dark", "system"];
const META: Record<Theme, { icon: string; label: string }> = {
  light: { icon: "☀️", label: "Terang" },
  dark: { icon: "🌙", label: "Gelap" },
  system: { icon: "🖥️", label: "Sistem" },
};

function systemDark(): boolean {
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function applyTheme(theme: Theme) {
  const dark = theme === "dark" || (theme === "system" && systemDark());
  document.documentElement.classList.toggle("dark", dark);
}

export default function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("system");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const stored = (localStorage.getItem(STORAGE_KEY) as Theme | null) ?? "system";
    setTheme(stored);
    setMounted(true);
  }, []);

  // Ikuti perubahan tema OS saat mode "system".
  useEffect(() => {
    if (theme !== "system") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => applyTheme("system");
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [theme]);

  function cycle() {
    const next = CYCLE[(CYCLE.indexOf(theme) + 1) % CYCLE.length];
    setTheme(next);
    localStorage.setItem(STORAGE_KEY, next);
    applyTheme(next);
  }

  // Hindari mismatch hydration: render placeholder sampai mounted.
  if (!mounted) {
    return <div className="h-9 w-9 rounded-full bg-neutral-200/60 dark:bg-neutral-800/60" />;
  }

  const meta = META[theme];
  return (
    <button
      type="button"
      onClick={cycle}
      title={`Tema: ${meta.label} (klik untuk ganti)`}
      aria-label={`Tema: ${meta.label}`}
      className="flex h-9 w-9 items-center justify-center rounded-full border border-c surface-2 text-base transition hover:bg-neutral-100 dark:hover:bg-neutral-800"
    >
      <span aria-hidden>{meta.icon}</span>
    </button>
  );
}
