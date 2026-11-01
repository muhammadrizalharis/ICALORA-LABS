"use client";

import { useEffect, useState } from "react";

type Theme = "light" | "dark" | "system";

const STORAGE_KEY = "theme";

function systemDark(): boolean {
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function applyTheme(theme: Theme) {
  const dark = theme === "dark" || (theme === "system" && systemDark());
  document.documentElement.classList.toggle("dark", dark);
}

const OPTIONS: { value: Theme; label: string; icon: string }[] = [
  { value: "light", label: "Terang", icon: "☀️" },
  { value: "dark", label: "Gelap", icon: "🌙" },
  { value: "system", label: "Sistem", icon: "🖥️" },
];

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

  function choose(next: Theme) {
    setTheme(next);
    localStorage.setItem(STORAGE_KEY, next);
    applyTheme(next);
  }

  // Hindari mismatch hydration: render placeholder sampai mounted.
  if (!mounted) {
    return <div className="h-9 rounded-lg bg-neutral-200/60 dark:bg-neutral-800/60" />;
  }

  return (
    <div className="flex gap-1 rounded-lg bg-neutral-200/70 p-1 dark:bg-neutral-800/70">
      {OPTIONS.map((opt) => {
        const active = theme === opt.value;
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() => choose(opt.value)}
            title={opt.label}
            aria-pressed={active}
            className={`flex-1 rounded-md px-2 py-1 text-xs font-medium transition ${
              active
                ? "bg-white text-neutral-900 shadow-sm dark:bg-neutral-950 dark:text-white"
                : "text-neutral-500 hover:text-neutral-800 dark:text-neutral-400 dark:hover:text-neutral-200"
            }`}
          >
            <span aria-hidden>{opt.icon}</span>
            <span className="ml-1">{opt.label}</span>
          </button>
        );
      })}
    </div>
  );
}
