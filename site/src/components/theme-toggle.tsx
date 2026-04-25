"use client"

import { useEffect, useState } from "react"

const THEME_STORAGE_KEY = "howoldisthisjob-theme"

function applyTheme(nextTheme: "light" | "dark") {
  document.documentElement.classList.toggle("dark", nextTheme === "dark")
  document.documentElement.style.colorScheme = nextTheme
}

function readInitialTheme(): "light" | "dark" {
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY)
    if (stored === "light" || stored === "dark") return stored
  } catch {}
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<"light" | "dark">(() =>
    typeof window === "undefined" ? "light" : readInitialTheme(),
  )

  useEffect(() => {
    applyTheme(theme)
  }, [theme])

  function toggleTheme() {
    const nextTheme = theme === "dark" ? "light" : "dark"
    setTheme(nextTheme)
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, nextTheme)
    } catch {}
  }

  return (
    <button
      type="button"
      onClick={toggleTheme}
      suppressHydrationWarning
      className="transition-colors hover:text-neutral-800 dark:hover:text-neutral-200"
      aria-label="Toggle color theme"
      title="Toggle color theme"
    >
      {theme === "dark" ? "Night" : "Day"}
    </button>
  )
}
