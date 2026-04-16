"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { createPortal } from "react-dom"

export type ToastVariant = "info" | "warn" | "error"

export type ToastItem = {
  id: string
  title?: string
  message: string
  variant?: ToastVariant
}

export function Toasts({
  items,
  onDismiss,
  ttlMs = 4500,
}: {
  items: ToastItem[]
  onDismiss: (id: string) => void
  ttlMs?: number
}) {
  const EXIT_MS = 180
  const [closingIds, setClosingIds] = useState<Set<string>>(new Set())
  const bornAtMs = useRef<Map<string, number>>(new Map())
  const autoCloseTimers = useRef<Map<string, number>>(new Map())
  const closeTimers = useRef<Map<string, number>>(new Map())

  const beginClose = useCallback((id: string, immediate = false) => {
    const existing = closeTimers.current.get(id)
    if (existing) {
      window.clearTimeout(existing)
    }

    setClosingIds((prev) => {
      if (prev.has(id)) return prev
      const next = new Set(prev)
      next.add(id)
      return next
    })

    const delay = immediate ? 0 : EXIT_MS
    const timer = window.setTimeout(() => {
      closeTimers.current.delete(id)
      setClosingIds((prev) => {
        if (!prev.has(id)) return prev
        const next = new Set(prev)
        next.delete(id)
        return next
      })
      onDismiss(id)
    }, delay)
    closeTimers.current.set(id, timer)
  }, [onDismiss])

  useEffect(() => {
    const now = Date.now()
    const ids = new Set(items.map((item) => item.id))

    for (const item of items) {
      if (!bornAtMs.current.has(item.id)) {
        bornAtMs.current.set(item.id, now)
      }
      if (autoCloseTimers.current.has(item.id)) continue
      if (closingIds.has(item.id)) continue

      const bornAt = bornAtMs.current.get(item.id) ?? now
      const elapsed = now - bornAt
      const waitMs = Math.max(0, ttlMs - EXIT_MS - elapsed)
      const timer = window.setTimeout(() => beginClose(item.id), waitMs)
      autoCloseTimers.current.set(item.id, timer)
    }

    autoCloseTimers.current.forEach((timer, id) => {
      if (ids.has(id)) return
      window.clearTimeout(timer)
      autoCloseTimers.current.delete(id)
    })

    closeTimers.current.forEach((timer, id) => {
      if (ids.has(id)) return
      window.clearTimeout(timer)
      closeTimers.current.delete(id)
    })

    bornAtMs.current.forEach((_, id) => {
      if (ids.has(id)) return
      bornAtMs.current.delete(id)
    })
  }, [beginClose, closingIds, items, ttlMs])

  useEffect(() => {
    const bornMap = bornAtMs.current
    const autoTimerMap = autoCloseTimers.current
    const timerMap = closeTimers.current
    return () => {
      autoTimerMap.forEach((timer) => window.clearTimeout(timer))
      autoTimerMap.clear()
      timerMap.forEach((timer) => window.clearTimeout(timer))
      timerMap.clear()
      bornMap.clear()
    }
  }, [])

  if (typeof document === "undefined" || items.length === 0) return null

  return createPortal(
    <div className="pointer-events-none fixed right-3 top-3 z-[60] flex justify-end sm:right-4 sm:top-4">
      <div className="flex w-full max-w-[300px] flex-col gap-2">
        {items.map((t) => (
          <div
            key={t.id}
            className={`toast-card pointer-events-auto relative rounded-lg border border-neutral-200 bg-white px-3 pb-3 pt-2 shadow-sm ${closingIds.has(t.id) ? "toast-card--exit" : "toast-card--enter"}`}
            role="status"
            aria-live="polite"
          >
            <button
              type="button"
              className="toast-close-btn absolute right-1.5 top-1.5"
              onClick={() => beginClose(t.id)}
              aria-label="Dismiss notification"
            >
              <span aria-hidden>×</span>
            </button>

            <div className="min-w-0 pr-6">
              {t.title && (
                <div className="text-xs font-medium text-neutral-900">
                  {t.title}
                </div>
              )}
              <div className="text-xs leading-relaxed text-neutral-700">
                {t.message}
              </div>
            </div>
            <div
              className="toast-progress absolute inset-x-0 bottom-0 h-0.5"
              style={{
                animationDuration: `${ttlMs}ms`,
              }}
            />
          </div>
        ))}
      </div>
    </div>
    ,
    document.body
  )
}

