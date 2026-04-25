"use client"

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react"

import {
  clearHistory,
  deleteHistoryItem,
  fetchHistory,
  type HistoryItem,
  saveToHistory,
  streamEstimateJobAge,
  type StreamEvent,
} from "@/lib/api"
import { INTERCEPTS, checkIntercept } from "@/lib/platforms"
import { cn } from "@/lib/utils"
import { ConfirmModal } from "@/components/confirm-modal"
import { PlatformCarousel } from "@/components/platform-carousel"
import {
  ProgressPipeline,
  type StageRow,
} from "@/components/progress-pipeline"
import { SearchHistory } from "@/components/search-history"
import { Toasts, type ToastItem, type ToastVariant } from "@/components/toasts"
import { SUPPORTED_PLATFORMS } from "@/lib/supported-platforms"

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

const HISTORY_CACHE_KEY = "howoldisthisjob-history"

function historyLookupKey(item: Pick<HistoryItem, "url" | "result">): string {
  const normalized = item.result.normalized_url?.trim()
  if (normalized) return normalized
  return item.url.trim()
}

function dedupeHistory(items: HistoryItem[]): HistoryItem[] {
  const seen = new Set<string>()
  const deduped: HistoryItem[] = []

  for (const item of items) {
    const key = historyLookupKey(item)
    if (seen.has(key)) continue
    seen.add(key)
    deduped.push(item)
  }

  return deduped
}

function mergeHistoryItem(items: HistoryItem[], nextItem: HistoryItem): HistoryItem[] {
  const nextKey = historyLookupKey(nextItem)
  const filtered = items.filter((item) => {
    if (item.id === nextItem.id) return false
    return historyLookupKey(item) !== nextKey
  })

  return [nextItem, ...filtered]
}

function readCachedHistory(): HistoryItem[] {
  try {
    const raw = localStorage.getItem(HISTORY_CACHE_KEY)
    return raw ? dedupeHistory(JSON.parse(raw) as HistoryItem[]) : []
  } catch {
    return []
  }
}

type ModalState =
  | {
      kind: "intercept"
      searchUrl: string
      title: string
      description: string
      confirmText: string
      cancelText: string | null
      action: "close" | "continue"
    }
  | {
      kind: "clear"
    }
  | null

function usePrefersReducedMotion() {
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false)

  useEffect(() => {
    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)")
    const update = () => setPrefersReducedMotion(mediaQuery.matches)

    update()
    mediaQuery.addEventListener("change", update)

    return () => mediaQuery.removeEventListener("change", update)
  }, [])

  return prefersReducedMotion
}

export function JobChecker() {
  const invalidShakeTimeoutRef = useRef<number>(0)
  const invalidShakeFrameRef = useRef<number>(0)
  const autoRunUrlRef = useRef<string | null>(null)
  const [url, setUrl] = useState("")
  const [urlError, setUrlError] = useState<string | null>(null)
  const [urlShake, setUrlShake] = useState(false)
  const [loading, setLoading] = useState(false)

  const [history, setHistory] = useState<HistoryItem[]>([])
  const [expandedIds, setExpandedIds] = useState<Set<string>>(() => new Set())

  const expandId = useCallback((id: string) => {
    setExpandedIds((prev) => {
      if (prev.has(id)) return prev
      const next = new Set(prev)
      next.add(id)
      return next
    })
  }, [])

  const collapseId = useCallback((id: string) => {
    setExpandedIds((prev) => {
      if (!prev.has(id)) return prev
      const next = new Set(prev)
      next.delete(id)
      return next
    })
  }, [])

  const toggleExpand = useCallback((id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])
  const [toasts, setToasts] = useState<ToastItem[]>([])
  const [modalState, setModalState] = useState<ModalState>(null)
  const [progressPlatform, setProgressPlatform] = useState<string | null>(null)
  const [progressStages, setProgressStages] = useState<StageRow[]>([])
  const prefersReducedMotion = usePrefersReducedMotion()

  // Pre-populate from localStorage before first paint to avoid flash of empty state
  useLayoutEffect(() => {
    const cached = readCachedHistory()
    if (cached.length > 0) {
      setHistory(cached)
      document.documentElement.setAttribute("data-has-history", "")
      return
    }

    document.documentElement.removeAttribute("data-has-history")
  }, [])

  // Keep localStorage in sync with any history change
  useEffect(() => {
    try {
      localStorage.setItem(HISTORY_CACHE_KEY, JSON.stringify(history))
    } catch {}
  }, [history])

  // Keep html[data-has-history] in sync so CSS reacts to runtime changes (loading, clear)
  useEffect(() => {
    if (history.length > 0 || loading) {
      document.documentElement.setAttribute("data-has-history", "")
    } else {
      document.documentElement.removeAttribute("data-has-history")
    }
  }, [history, loading])

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
    setUrlError("Please enter a full http or https URL.")
    if (prefersReducedMotion) return
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
  }, [prefersReducedMotion])

  useEffect(() => {
    let cancelled = false

    async function loadHistory() {
      try {
        const items = dedupeHistory(await fetchHistory())
        if (cancelled) return
        setHistory(items)
        if (items.length > 0) expandId(items[0].id)
      } catch {
        if (cancelled) return
        pushToast("Couldn’t load history.", "error")
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
    setProgressPlatform(null)
    setProgressStages([])
    try {
      const onEvent = (event: StreamEvent) => {
        if (event.type === "platform") {
          setProgressPlatform(event.platform)
          return
        }
        if (event.type === "stage") {
          setProgressStages((current) => {
            if (event.status === "start") {
              return [...current, { label: event.label, status: "running" }]
            }
            const nextStatus: StageRow["status"] =
              event.status === "ok" ? "ok" : "warn"
            // Update the last matching running row; if none, append.
            for (let i = current.length - 1; i >= 0; i -= 1) {
              if (current[i].label === event.label && current[i].status === "running") {
                const next = current.slice()
                next[i] = {
                  label: event.label,
                  status: nextStatus,
                  detail: event.detail,
                }
                return next
              }
            }
            return [
              ...current,
              { label: event.label, status: nextStatus, detail: event.detail },
            ]
          })
        }
      }
      const result = await streamEstimateJobAge(searchUrl, onEvent)
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
      setHistory((current) => mergeHistoryItem(current, item))
      expandId(item.id)
      setUrl("")
    } catch {
      pushToast("Couldn’t reach that URL.", "error")
    } finally {
      setLoading(false)
      setProgressPlatform(null)
      setProgressStages([])
    }
  }, [expandId, pushToast])

  const submitValidatedUrl = useCallback(
    (validated: string, rawInput: string = validated) => {
      const existing = history.find((item) => item.url === validated)
      if (existing) {
        expandId(existing.id)
        return
      }

      const matched = checkIntercept(rawInput)
      if (matched) {
        const spec = INTERCEPTS[matched]
        setModalState({
          kind: "intercept",
          searchUrl: validated,
          title: spec.title,
          description: spec.body,
          confirmText:
            spec.mode === "blocked"
              ? spec.dismissLabel
              : (spec.continueLabel ?? "Continue"),
          cancelText: spec.mode === "blocked" ? null : spec.dismissLabel,
          action: spec.mode === "blocked" ? "close" : "continue",
        })
        return
      }

      runCheck(validated)
    },
    [expandId, history, runCheck],
  )

  const confirmModal = useCallback(async () => {
    if (!modalState) return

    if (modalState.kind === "intercept") {
      setModalState(null)
      if (modalState.action === "continue") {
        runCheck(modalState.searchUrl)
      }
      return
    }

    setModalState(null)
    try {
      await clearHistory()
    } catch {
      pushToast("Couldn’t clear history.", "error")
      return
    }
    setHistory([])
    setExpandedIds(new Set())
  }, [modalState, pushToast, runCheck])

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const trimmed = url.trim()
    if (!trimmed) return

    const validated = validateHttpUrl(trimmed)
    if (!validated) {
      triggerInvalidUrlFeedback()
      return
    }
    setUrlError(null)
    submitValidatedUrl(validated, trimmed)
  }

  const handleRemove = useCallback(
    async (id: string) => {
      try {
        await deleteHistoryItem(id)
        setHistory((current) => current.filter((item) => item.id !== id))
      } catch {
        pushToast("Couldn’t remove that entry.", "error")
        return
      }
      collapseId(id)
    },
    [collapseId, pushToast],
  )

  function handleClearAll() {
    setModalState({ kind: "clear" })
  }

  const hasHistory = history.length > 0

  const placeholder = useTypingPlaceholder(
    PLACEHOLDER_URLS,
    prefersReducedMotion || !!url || loading || hasHistory,
  )

  useEffect(() => {
    if (loading || autoRunUrlRef.current !== null) return

    const seeded = new URLSearchParams(window.location.search).get("url")?.trim()
    if (!seeded) {
      autoRunUrlRef.current = ""
      return
    }

    autoRunUrlRef.current = seeded
    setUrl(seeded)

    const validated = validateHttpUrl(seeded)
    if (!validated) {
      triggerInvalidUrlFeedback()
      return
    }

    setUrlError(null)
    submitValidatedUrl(validated, seeded)
  }, [loading, submitValidatedUrl, triggerInvalidUrlFeedback])

  return (
    <>
      <Toasts items={toasts} onDismiss={dismissToast} />
      <ConfirmModal
        open={modalState !== null}
        title={
          modalState?.kind === "intercept"
            ? modalState.title
            : "Clear your search history?"
        }
        description={
          modalState?.kind === "intercept"
            ? modalState.description
            : "This will permanently remove every saved result from your history on this device."
        }
        confirmText={
          modalState?.kind === "intercept"
            ? modalState.confirmText
            : "Clear all"
        }
        cancelText={modalState?.kind === "intercept" ? modalState.cancelText : "Cancel"}
        destructive={modalState?.kind === "clear"}
        onConfirm={confirmModal}
        onCancel={() => setModalState(null)}
      />
      <div className="flex w-full flex-col gap-6">
        <div className="flex flex-col gap-2">
          <form
            onSubmit={onSubmit}
            noValidate
            className="flex w-full flex-col gap-2 sm:flex-row sm:items-stretch"
          >
            <input
              type="text"
              inputMode="url"
              autoComplete="url"
              spellCheck={false}
              required
              placeholder={url || hasHistory ? "https://careers.example.com/jobs/123" : placeholder}
              value={url}
              onChange={(event) => {
                setUrl(event.target.value)
                if (urlError) setUrlError(null)
              }}
              aria-label="Job posting URL"
              aria-invalid={!!urlError}
              aria-describedby={urlError ? "job-url-error" : undefined}
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
          <div className="min-h-5 px-1">
            {urlError && (
              <p
                id="job-url-error"
                role="alert"
                className="text-xs text-red-600 dark:text-red-400"
              >
                {urlError}
              </p>
            )}
          </div>
        </div>

        {loading && (
          <ProgressPipeline
            platform={progressPlatform}
            stages={progressStages}
          />
        )}

        {hasHistory && (
          <SearchHistory
            items={history}
            expandedIds={expandedIds}
            onToggleExpand={toggleExpand}
            onRemove={handleRemove}
            onClearAll={handleClearAll}
          />
        )}

        {!hasHistory && !loading && (
          <div className="flex flex-col gap-4 -mx-6">
            <p className="px-6 text-xs text-neutral-500 dark:text-neutral-400">
              {SUPPORTED_PLATFORMS.length}+ platforms supported
            </p>
            <PlatformCarousel />
          </div>
        )}

      </div>
    </>
  )
}
