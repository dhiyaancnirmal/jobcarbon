"use client"

import { useCallback, useEffect, useRef, useState } from "react"

import {
  clearHistory,
  deleteHistoryItem,
  estimateJobAge,
  fetchHistory,
  type HistoryItem,
  saveToHistory,
} from "@/lib/api"
import { INTERCEPTS, checkIntercept } from "@/lib/platforms"
import { cn } from "@/lib/utils"
import { PlatformCarousel } from "@/components/platform-carousel"
import { SearchHistory } from "@/components/search-history"
import { Toasts, type ToastItem, type ToastVariant } from "@/components/toasts"

const PLACEHOLDER_URLS = [
  "https://jobs.lever.co/stripe/abc123",
  "https://boards.greenhouse.io/stripe/jobs/1234",
  "https://jobs.ashbyhq.com/stripe/abc123",
  "https://jobs.workable.com/view/abc123",
  "https://jobs.teamtailor.com/jobs/123-senior-engineer",
  "https://company.recruitee.com/o/senior-engineer",
  "https://company.jobs.personio.de/job/1234",
  "https://jobs.breezy.hr/p/abc123",
  "https://company.bamboohr.com/careers/123",
  "https://app.careers.page/abc123",
]

function useTypingPlaceholder(urls: string[], paused: boolean) {
  const first = urls[0] ?? ""
  // Start at the full first URL so SSR + first client paint match (avoids hydration mismatch).
  const [placeholder, setPlaceholder] = useState(first)
  const indexRef = useRef(0)
  const directionRef = useRef<1 | -1>(-1)
  const charRef = useRef(first.length)
  const rafRef = useRef<number>(0)
  const lastTickRef = useRef(0)

  useEffect(() => {
    if (paused) {
      cancelAnimationFrame(rafRef.current)
      return
    }

    const typeSpeed = 40
    const deleteSpeed = 25
    const pauseAfterType = 2000
    const pauseAfterDelete = 300

    function tick(now: number) {
      const target = urls[indexRef.current % urls.length]
      const speed = directionRef.current === 1 ? typeSpeed : deleteSpeed
      const elapsed = now - lastTickRef.current

      if (elapsed < speed) {
        rafRef.current = requestAnimationFrame(tick)
        return
      }

      lastTickRef.current = now

      if (directionRef.current === 1) {
        charRef.current += 1
        setPlaceholder(target.slice(0, charRef.current))
        if (charRef.current >= target.length) {
          directionRef.current = -1
          lastTickRef.current = now + pauseAfterType
        }
      } else {
        charRef.current -= 1
        setPlaceholder(target.slice(0, charRef.current))
        if (charRef.current <= 0) {
          directionRef.current = 1
          indexRef.current = (indexRef.current + 1) % urls.length
          lastTickRef.current = now + pauseAfterDelete
        }
      }

      rafRef.current = requestAnimationFrame(tick)
    }

    lastTickRef.current = performance.now()
    rafRef.current = requestAnimationFrame(tick)

    return () => cancelAnimationFrame(rafRef.current)
  }, [urls, paused])

  return placeholder
}

export function JobChecker() {
  const invalidShakeTimeoutRef = useRef<number>(0)
  const invalidShakeFrameRef = useRef<number>(0)
  const [url, setUrl] = useState("")
  const [urlError, setUrlError] = useState(false)
  const [urlShake, setUrlShake] = useState(false)
  const [loading, setLoading] = useState(false)
  const [historyReady, setHistoryReady] = useState(false)

  const [history, setHistory] = useState<HistoryItem[]>([])
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [toasts, setToasts] = useState<ToastItem[]>([])

  const dismissToast = useCallback((id: string) => {
    setToasts((cur) => cur.filter((t) => t.id !== id))
  }, [])

  const pushToast = useCallback(
    (message: string, variant: ToastVariant = "info", title?: string) => {
      const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`
      setToasts((cur) => [
        ...cur.slice(Math.max(0, cur.length - 2)),
        { id, title, message, variant },
      ])
    },
    [],
  )

  function validateHttpUrl(raw: string): string | null {
    try {
      const parsed = new URL(raw)
      if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return null
      return parsed.toString()
    } catch {
      return null
    }
  }

  const triggerInvalidUrlFeedback = useCallback(() => {
    setUrlError(true)
    setUrlShake(false)

    if (invalidShakeTimeoutRef.current) {
      window.clearTimeout(invalidShakeTimeoutRef.current)
    }
    if (invalidShakeFrameRef.current) {
      window.cancelAnimationFrame(invalidShakeFrameRef.current)
    }

    invalidShakeFrameRef.current = window.requestAnimationFrame(() => {
      setUrlShake(true)
      invalidShakeTimeoutRef.current = window.setTimeout(() => {
        setUrlShake(false)
      }, 360)
    })
  }, [])

  useEffect(() => {
    let cancelled = false

    async function loadHistory() {
      try {
        const items = await fetchHistory()
        if (cancelled) return
        setHistory(items)
        if (items.length > 0) setExpandedId(items[0].id)
      } catch {
        if (cancelled) return
        pushToast("Couldn’t load history.", "error")
      } finally {
        if (!cancelled) setHistoryReady(true)
      }
    }

    loadHistory()

    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    return () => {
      if (invalidShakeTimeoutRef.current) {
        window.clearTimeout(invalidShakeTimeoutRef.current)
      }
      if (invalidShakeFrameRef.current) {
        window.cancelAnimationFrame(invalidShakeFrameRef.current)
      }
    }
  }, [])

  const runCheck = useCallback(async (searchUrl: string) => {
    setLoading(true)
    try {
      const result = await estimateJobAge(searchUrl)
      if (result.status !== "success") {
        const message =
          result.status === "blocked"
            ? `${result.platform} blocks automated access.`
            : result.status === "unsupported"
              ? `${result.platform} doesn’t expose reliable posting dates.`
              : "No posting date found for that URL."
        const variant = result.status === "blocked" ? "warn" : "info"
        pushToast(message, variant)
        return
      }
      const item = await saveToHistory(searchUrl, result)
      setHistory((current) => [item, ...current])
      setExpandedId(item.id)
      setUrl("")
    } catch {
      pushToast("Couldn’t reach that URL.", "error")
    } finally {
      setLoading(false)
    }
  }, [pushToast])

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const trimmed = url.trim()
    if (!trimmed) return

    const validated = validateHttpUrl(trimmed)
    if (!validated) {
      triggerInvalidUrlFeedback()
      return
    }
    setUrlError(false)

    const existing = history.find((item) => item.url === validated)
    if (existing) {
      setExpandedId(existing.id)
      return
    }

    const matched = checkIntercept(trimmed)
    if (matched) {
      const spec = INTERCEPTS[matched]
      if (spec.mode === "blocked") {
        pushToast(spec.title, "warn")
        return
      }
      pushToast(spec.title, "info")
    }
    runCheck(validated)
  }

  async function handleRemove(id: string) {
    try {
      await deleteHistoryItem(id)
      setHistory((current) => current.filter((item) => item.id !== id))
    } catch {
      pushToast("Couldn’t remove that entry.", "error")
      return
    }
    if (expandedId === id) setExpandedId(null)
  }

  async function handleClearAll() {
    try {
      await clearHistory()
    } catch {
      pushToast("Couldn’t clear history.", "error")
      return
    }
    setHistory([])
    setExpandedId(null)
  }

  const placeholder = useTypingPlaceholder(PLACEHOLDER_URLS, !!url || loading)

  const hasHistory = history.length > 0

  return (
    <>
      <Toasts items={toasts} onDismiss={dismissToast} />
      <div
        className="flex w-full flex-col gap-6"
        data-has-history={hasHistory || loading ? "true" : undefined}
      >
      <div className="flex flex-col gap-2">
        <form
          onSubmit={onSubmit}
          noValidate
          className="flex w-full flex-col gap-2 sm:flex-row sm:items-stretch"
        >
          <input
            type="url"
            required
            placeholder={url ? "https://careers.example.com/jobs/…" : placeholder}
            value={url}
            onChange={(event) => {
              setUrl(event.target.value)
              if (urlError) setUrlError(false)
            }}
            aria-label="Job posting URL"
            className={cn(
              "gel-input min-h-11 min-w-0 w-full flex-1 text-[15px] disabled:cursor-not-allowed",
              urlError && "gel-input--invalid",
              urlShake && "url-input--shake",
            )}
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading}
            className="gel-btn gel-btn--save w-full shrink-0 sm:w-auto"
          >
            {loading ? (
              <span className="inline-flex items-center justify-center gap-2">
                <span
                  aria-hidden="true"
                  className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white"
                />
                Checking…
              </span>
            ) : (
              "Check"
            )}
          </button>
        </form>
      </div>

      {hasHistory && (
        <SearchHistory
          items={history}
          expandedId={expandedId}
          onToggleExpand={setExpandedId}
          onRemove={handleRemove}
          onClearAll={handleClearAll}
        />
      )}

      {historyReady && !hasHistory && !loading && (
        <div className="flex flex-col gap-4 -mx-6">
          <p className="px-6 text-xs text-neutral-400">23+ platforms supported</p>
          <PlatformCarousel />
        </div>
      )}

      </div>
    </>
  )
}
