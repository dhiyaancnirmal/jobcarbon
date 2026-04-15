"use client"

import { useCallback, useEffect, useState } from "react"

import {
  clearHistory,
  deleteHistoryItem,
  estimateJobAge,
  fetchHistory,
  type HistoryItem,
  saveToHistory,
} from "@/lib/api"
import { checkIntercept, type InterceptPlatform } from "@/lib/platforms"
import { PlatformCarousel } from "@/components/platform-carousel"
import { Spinner } from "@/components/spinner"
import { SearchHistory } from "@/components/search-history"
import { PlatformDialog } from "@/components/platform-dialog"
import { ConfirmModal } from "@/components/confirm-modal"

const EXAMPLE_URLS = [
  "https://jobs.lever.co/acme/abc-123-def",
  "https://boards.greenhouse.io/acme/jobs/123456",
  "https://jobs.ashbyhq.com/acme/abc-123-def",
  "https://jobs.smartrecruiters.com/ACME/123456",
  "https://apply.workable.com/job/abc123",
  "https://acme.wd1.myworkdayjobs.com/en-US/acme/job/senior-engineer",
  "https://ats.rippling.com/acme/jobs/abc-123",
  "https://careers.icims.com/jobs/12345/senior-engineer",
  "https://signal1.bamboohr.com/careers/39",
  "https://jobs.jobvite.com/acme/job/oD2D4fw6",
]

export function JobChecker() {
  const [url, setUrl] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [placeholder, setPlaceholder] = useState("")
  const [historyReady, setHistoryReady] = useState(false)

  const [history, setHistory] = useState<HistoryItem[]>([])
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [intercept, setIntercept] = useState<{
    platform: InterceptPlatform | null
    url: string
  }>({ platform: null, url: "" })
  const [confirmClear, setConfirmClear] = useState(false)
  const placeholderAnimationPaused = loading || url.trim().length > 0

  useEffect(() => {
    let cancelled = false

    async function loadHistory() {
      try {
        const items = await fetchHistory()
        if (cancelled) return
        setHistory(items)
        if (items.length > 0) setExpandedId(items[0].id)
      } catch (err) {
        if (cancelled) return
        setError(err instanceof Error ? err.message : "Could not load history.")
      } finally {
        if (!cancelled) setHistoryReady(true)
      }
    }

    loadHistory()

    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (placeholderAnimationPaused) {
      setPlaceholder("")
      return
    }

    let idx = 0
    let pos = 0
    let deleting = false
    let timeout: ReturnType<typeof setTimeout>

    function tick() {
      const current = EXAMPLE_URLS[idx]
      if (!deleting) {
        pos++
        setPlaceholder(current.slice(0, pos))
        if (pos >= current.length) {
          deleting = true
          timeout = setTimeout(tick, 2000)
          return
        }
        timeout = setTimeout(tick, 45)
      } else {
        pos--
        setPlaceholder(current.slice(0, pos))
        if (pos <= 0) {
          deleting = false
          idx = (idx + 1) % EXAMPLE_URLS.length
          timeout = setTimeout(tick, 300)
          return
        }
        timeout = setTimeout(tick, 25)
      }
    }

    tick()
    return () => clearTimeout(timeout)
  }, [placeholderAnimationPaused])

  const runCheck = useCallback(async (searchUrl: string) => {
    setLoading(true)
    setError(null)
    try {
      const result = await estimateJobAge(searchUrl)
      const item = await saveToHistory(searchUrl, result)
      setHistory((current) => [item, ...current])
      setExpandedId(item.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.")
      setUrl(searchUrl)
    } finally {
      setLoading(false)
    }
  }, [])

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const trimmed = url.trim()
    if (!trimmed) return

    const matched = checkIntercept(trimmed)
    if (matched) {
      setIntercept({ platform: matched, url: trimmed })
      return
    }
    runCheck(trimmed)
  }

  function handleInterceptContinue() {
    const u = intercept.url
    setIntercept({ platform: null, url: "" })
    runCheck(u)
  }

  function handleInterceptCancel() {
    setIntercept({ platform: null, url: "" })
  }

  async function handleRecheck(item: HistoryItem) {
    setLoading(true)
    setError(null)
    try {
      const result = await estimateJobAge(item.url)
      await deleteHistoryItem(item.id)
      const updated = await saveToHistory(item.url, result)
      setHistory((current) => [updated, ...current.filter((entry) => entry.id !== item.id)])
      setExpandedId(updated.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.")
    } finally {
      setLoading(false)
    }
  }

  async function handleRemove(id: string) {
    try {
      await deleteHistoryItem(id)
      setHistory((current) => current.filter((item) => item.id !== id))
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not remove this entry.")
      return
    }
    if (expandedId === id) setExpandedId(null)
  }

  async function handleClearAll() {
    try {
      await clearHistory()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not clear history.")
      setConfirmClear(false)
      return
    }
    setHistory([])
    setExpandedId(null)
    setConfirmClear(false)
  }

  const hasHistory = history.length > 0

  return (
    <div className="flex w-full flex-col gap-6">
      <div className="flex flex-col gap-2">
        <form onSubmit={onSubmit} noValidate className="flex w-full gap-2">
          <input
            type="url"
            required
            placeholder={placeholder}
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            className="h-10 flex-1 rounded-lg border border-neutral-200 bg-white px-3 text-sm text-neutral-900 outline-none transition-colors placeholder:text-neutral-400 focus:border-neutral-400 disabled:opacity-50"
            disabled={loading}
            suppressHydrationWarning
          />
          <button
            type="submit"
            disabled={loading}
            className={`gel-btn gel-btn--save ${loading ? "gel-btn--loading" : ""}`}
          >
            {loading ? (
              <Spinner className="text-white" />
            ) : (
              "Check"
            )}
          </button>
        </form>
        {error && <p className="px-1 text-xs text-red-600">{error}</p>}
      </div>

      {hasHistory && (
        <SearchHistory
          items={history}
          expandedId={expandedId}
          onToggleExpand={setExpandedId}
          onRecheck={handleRecheck}
          onRemove={handleRemove}
          onClearAll={() => setConfirmClear(true)}
        />
      )}

      {historyReady && !hasHistory && !loading && (
        <div className="flex flex-col gap-4 -mx-6">
          <p className="px-6 text-xs text-neutral-400">23+ platforms supported</p>
          <PlatformCarousel />
        </div>
      )}

      <PlatformDialog
        platform={intercept.platform}
        onContinue={handleInterceptContinue}
        onCancel={handleInterceptCancel}
      />

      <ConfirmModal
        open={confirmClear}
        title="Clear search history?"
        description="This removes every saved entry tied to your anonymous session."
        confirmText="Clear all"
        cancelText="Cancel"
        destructive
        onConfirm={handleClearAll}
        onCancel={() => setConfirmClear(false)}
      />
    </div>
  )
}
