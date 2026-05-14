"use client"

import { useEffect, useState } from "react"

const THEME_STORAGE_KEY = "howoldisthisjob-theme"

type ThemePreference = "system" | "light" | "dark"
type ResolvedTheme = "light" | "dark"

function systemTheme(): ResolvedTheme {
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"
}

function applyTheme(nextTheme: ResolvedTheme) {
  document.documentElement.classList.toggle("dark", nextTheme === "dark")
  document.documentElement.style.colorScheme = nextTheme
}

function readInitialPreference(): ThemePreference {
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY)
    if (stored === "light" || stored === "dark") return stored
  } catch {}
  return "system"
}

function resolveTheme(preference: ThemePreference): ResolvedTheme {
  return preference === "system" ? systemTheme() : preference
}

function nextPreference(preference: ThemePreference): ThemePreference {
  if (preference === "system") return "light"
  if (preference === "light") return "dark"
  return "system"
}

function persistPreference(preference: ThemePreference) {
  try {
    if (preference === "system") {
      window.localStorage.removeItem(THEME_STORAGE_KEY)
    } else {
      window.localStorage.setItem(THEME_STORAGE_KEY, preference)
    }
  } catch {}
}

function preferenceLabel(preference: ThemePreference) {
  if (preference === "system") return "System"
  return preference === "dark" ? "Night" : "Day"
}

export function ThemeToggle() {
  const [preference, setPreference] = useState<ThemePreference>(() =>
    typeof window === "undefined" ? "system" : readInitialPreference(),
  )

  useEffect(() => {
    applyTheme(resolveTheme(preference))

    if (preference !== "system") return

    const media = window.matchMedia("(prefers-color-scheme: dark)")
    function onSystemThemeChange() {
      applyTheme(resolveTheme("system"))
    }

    media.addEventListener("change", onSystemThemeChange)
    return () => media.removeEventListener("change", onSystemThemeChange)
  }, [preference])

  function toggleTheme() {
    setPreference((current) => {
      const next = nextPreference(current)
      persistPreference(next)
      applyTheme(resolveTheme(next))
      return next
    })
  }

  return (
    <button
      type="button"
      onClick={toggleTheme}
      suppressHydrationWarning
      className="transition-colors hover:text-neutral-800 dark:hover:text-neutral-200"
      aria-label={`Color theme: ${preferenceLabel(preference)}`}
      title={`Color theme: ${preferenceLabel(preference)}`}
    >
      {preferenceLabel(preference)}
    </button>
  )
}
