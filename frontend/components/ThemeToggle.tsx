"use client";

import { useEffect, useState } from "react";
import Icon from "@/components/Icon";

const STORAGE_KEY = "cmpdi-theme";

function applyTheme(dark: boolean) {
  const root = document.documentElement;
  root.classList.toggle("dark", dark);
  root.style.colorScheme = dark ? "dark" : "light";
  try {
    localStorage.setItem(STORAGE_KEY, dark ? "dark" : "light");
  } catch {
    /* private mode — class-only theming still works */
  }
}

export default function ThemeToggle() {
  const [dark, setDark] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setDark(document.documentElement.classList.contains("dark"));
    setMounted(true);
  }, []);

  function toggle() {
    const next = !dark;
    setDark(next);
    applyTheme(next);
  }

  if (!mounted) {
    return (
      <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-coal-200 dark:border-slate-700" />
    );
  }

  return (
    <button
      type="button"
      onClick={toggle}
      title={dark ? "Switch to light theme" : "Switch to dark theme"}
      aria-label="Toggle color theme"
      className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-coal-200 bg-white text-coal-600 shadow-card transition-colors hover:border-coal-400 hover:text-coal-900 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:border-slate-600 dark:hover:text-white"
    >
      {dark ? (
        <Icon name="sun" size={16} />
      ) : (
        <Icon name="moon" size={16} />
      )}
    </button>
  );
}