"use client"

import { Moon } from "lucide-react"
import { useState } from "react"

const THEME_STORAGE_KEY = "jobcarbon-theme"

function applyTheme(nextTheme: "light" | "dark") {
  document.documentElement.classList.toggle("dark", nextTheme === "dark")
  document.documentElement.style.colorScheme = nextTheme
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    if (typeof window === "undefined") {
      return "light"
    }
    try {
      const stored = window.localStorage.getItem(THEME_STORAGE_KEY)
      if (stored === "light" || stored === "dark") {
        return stored
      }
    } catch {}
    return window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light"
  })

  function toggleTheme() {
    const nextTheme = theme === "dark" ? "light" : "dark"
    setTheme(nextTheme)
    applyTheme(nextTheme)
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, nextTheme)
    } catch {}
  }

  return (
    <button
      type="button"
      onClick={toggleTheme}
      className="gel-btn gel-btn--sm gel-btn--neutral"
      aria-label="Toggle color theme"
      title="Toggle color theme"
    >
      <Moon className="size-3.5 text-neutral-600 dark:text-neutral-200" strokeWidth={1.9} aria-hidden />
      <span>Theme</span>
    </button>
  )
}
