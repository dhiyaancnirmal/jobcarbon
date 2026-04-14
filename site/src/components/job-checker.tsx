"use client"

import { useEffect, useState } from "react"

import { estimateJobAge, type EstimateResult } from "@/lib/api"

type State =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; result: EstimateResult }
  | { status: "error"; message: string }

function formatAge(days: number | null): string {
  if (days === null) return "Unknown"
  if (days === 0) return "Today"
  if (days === 1) return "1 day old"
  if (days < 30) return `${days} days old`
  const months = Math.floor(days / 30)
  if (months < 12) {
    return months === 1 ? "~1 month old" : `~${months} months old`
  }
  const years = Math.floor(days / 365)
  return years === 1 ? "~1 year old" : `~${years} years old`
}

function formatDate(iso: string | null): string | null {
  if (!iso) return null
  return new Date(iso + "T00:00:00").toLocaleDateString("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
  })
}

const confidenceColors: Record<string, string> = {
  high: "bg-emerald-50 text-emerald-700",
  medium: "bg-amber-50 text-amber-700",
  low: "bg-orange-50 text-orange-700",
  unknown: "bg-neutral-100 text-neutral-500",
}

const reliabilityDot: Record<string, string> = {
  high: "bg-emerald-500",
  medium: "bg-amber-500",
  low: "bg-orange-500",
}

const kindLabel: Record<string, string> = {
  posted: "Posted",
  published: "Published",
  refresh: "Refreshed",
  updated: "Updated",
  crawl: "Crawled",
  archive: "Archived",
  ceiling: "Ceiling",
  modified: "Modified",
}

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
  const [state, setState] = useState<State>({ status: "idle" })
  const [placeholder, setPlaceholder] = useState("")

  useEffect(() => {
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
  }, [])

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const trimmed = url.trim()
    if (!trimmed) return

    setState({ status: "loading" })
    try {
      const result = await estimateJobAge(trimmed)
      setState({ status: "success", result })
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Something went wrong."
      setState({ status: "error", message })
    }
  }

  const loading = state.status === "loading"

  return (
    <div className="flex w-full flex-col gap-6">
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
          {loading ? "Checking" : "Check"}
        </button>
      </form>

      {state.status === "error" && (
        <p className="text-sm text-red-600">{state.message}</p>
      )}

      {state.status === "success" && <ResultCard result={state.result} />}
    </div>
  )
}

function StatusMessage({ result }: { result: EstimateResult }) {
  if (result.status === "blocked") {
    return (
      <div className="flex flex-col gap-2 rounded-xl border border-amber-200 bg-amber-50 px-5 py-4">
        <div className="flex items-center gap-2">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-amber-600">
            <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
            <line x1="12" y1="9" x2="12" y2="13" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
          <span className="text-sm font-medium text-amber-800">Platform blocks automated access</span>
        </div>
        <p className="text-xs text-amber-700 leading-relaxed">
          {result.warnings[0] ?? `${result.platform} blocks automated access. Try the original company careers page URL instead.`}
        </p>
      </div>
    )
  }

  if (result.status === "unsupported") {
    return (
      <div className="flex flex-col gap-2 rounded-xl border border-neutral-200 bg-neutral-50 px-5 py-4">
        <div className="flex items-center gap-2">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-neutral-500">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="16" x2="12" y2="12" />
            <line x1="12" y1="8" x2="12.01" y2="8" />
          </svg>
          <span className="text-sm font-medium text-neutral-700">Platform not supported</span>
        </div>
        <p className="text-xs text-neutral-500 leading-relaxed">
          {result.warnings[0] ?? `${result.platform} does not expose reliable posting dates.`}
        </p>
      </div>
    )
  }

  if (result.status === "no_date") {
    return (
      <div className="flex flex-col gap-2 rounded-xl border border-neutral-200 bg-white px-5 py-4">
        <div className="flex items-center gap-2">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-neutral-400">
            <circle cx="12" cy="12" r="10" />
            <polyline points="12 6 12 12 16 14" />
          </svg>
          <span className="text-sm font-medium text-neutral-700">No posting date found</span>
        </div>
        <p className="text-xs text-neutral-500 leading-relaxed">
          We checked structured data, ATS APIs, and archives but couldn&apos;t find a reliable posting date for this listing.
        </p>
        {result.warnings.length > 0 && (
          <div className="mt-1 flex flex-col gap-1">
            {result.warnings.map((w, i) => (
              <p key={i} className="text-[11px] text-neutral-400">{w}</p>
            ))}
          </div>
        )}
      </div>
    )
  }

  return null
}

function ResultCard({ result }: { result: EstimateResult }) {
  if (result.status !== "success") {
    return <StatusMessage result={result} />
  }

  const dateStr = formatDate(result.likely_posted_date)
  const hasMeta = result.title || result.company || result.location || result.employment_type
  const hasInsights = Object.keys(result.hidden_insights).length > 0
  const hasWarnings = result.warnings.length > 0

  return (
    <div className="flex flex-col rounded-xl border border-neutral-200 bg-white overflow-hidden">
      <div className="flex items-start justify-between px-5 py-4">
        <div className="flex flex-col gap-1">
          <span className="text-xl font-semibold text-neutral-900">
            {formatAge(result.likely_age_days)}
          </span>
          {dateStr && (
            <span className="text-xs text-neutral-400">Posted {dateStr}</span>
          )}
        </div>
        <span
          className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-medium ${confidenceColors[result.confidence]}`}
        >
          {result.confidence} confidence
        </span>
      </div>

      {result.reposted_likely && (
        <div className="flex items-center gap-2 border-t border-amber-100 bg-amber-50/60 px-5 py-2">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="shrink-0 text-amber-600">
            <polyline points="23 4 23 10 17 10" />
            <polyline points="1 20 1 14 7 14" />
            <path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15" />
          </svg>
          <span className="text-[11px] font-medium text-amber-700">Likely reposted — original listing may be older than shown</span>
        </div>
      )}

      {hasMeta && (
        <div className="flex flex-col gap-1 border-t border-neutral-100 px-5 py-3">
          {result.title && (
            <span className="text-sm font-medium text-neutral-800">{result.title}</span>
          )}
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            {result.company && (
              <span className="text-xs text-neutral-500">{result.company}</span>
            )}
            {result.location && (
              <span className="text-xs text-neutral-400">{result.location}</span>
            )}
            {result.employment_type && (
              <span className="text-xs text-neutral-400">{result.employment_type}</span>
            )}
          </div>
        </div>
      )}

      {result.summary && (
        <div className="border-t border-neutral-100 px-5 py-3">
          <p className="text-xs text-neutral-500 leading-relaxed">{result.summary}</p>
        </div>
      )}

      <div className="flex items-center gap-2 border-t border-neutral-100 px-5 py-2.5">
        <span className="rounded bg-neutral-100 px-1.5 py-0.5 text-[11px] font-medium text-neutral-500">
          {result.platform}
        </span>
        {result.chosen_source && (
          <>
            <span className="text-[11px] text-neutral-400">
              via {result.chosen_source.source}
              {result.chosen_source.field && `.${result.chosen_source.field}`}
            </span>
            <span className={`inline-block h-1.5 w-1.5 rounded-full ${reliabilityDot[result.chosen_source.reliability]}`} />
          </>
        )}
      </div>

      {result.all_dates.length > 0 && (
        <div className="border-t border-neutral-100">
          <details>
            <summary className="cursor-pointer px-5 py-2.5 text-[11px] font-medium text-neutral-400 transition-colors hover:text-neutral-600">
              Evidence ({result.all_dates.length} date{result.all_dates.length !== 1 ? "s" : ""} found)
            </summary>
            <div className="border-t border-neutral-100">
              {result.all_dates.map((item, i) => (
                <div
                  key={i}
                  className="flex items-start gap-3 px-5 py-2 text-[11px] border-b border-neutral-50 last:border-b-0"
                >
                  <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center">
                    <span className={`inline-block h-1.5 w-1.5 rounded-full ${reliabilityDot[item.reliability]}`} />
                  </span>
                  <div className="flex flex-1 flex-col gap-0.5">
                    <div className="flex items-baseline gap-2">
                      <span className="font-mono text-neutral-700">{item.date}</span>
                      <span className="text-neutral-400">
                        {kindLabel[item.kind] ?? item.kind}
                      </span>
                    </div>
                    <span className="text-neutral-400">
                      {item.source}{item.field ? `.${item.field}` : ""}
                    </span>
                    {item.note && (
                      <span className="text-neutral-400 italic">{item.note}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </details>
        </div>
      )}

      {hasInsights && (
        <div className="border-t border-neutral-100">
          <details>
            <summary className="cursor-pointer px-5 py-2.5 text-[11px] font-medium text-neutral-400 transition-colors hover:text-neutral-600">
              Hidden insights ({Object.keys(result.hidden_insights).length})
            </summary>
            <div className="border-t border-neutral-100">
              {Object.entries(result.hidden_insights).map(([key, value]) => (
                <div
                  key={key}
                  className="flex items-baseline gap-2 px-5 py-2 text-[11px] border-b border-neutral-50 last:border-b-0"
                >
                  <span className="shrink-0 text-neutral-400">{key}</span>
                  <span className="truncate font-mono text-neutral-600">
                    {typeof value === "string" ? value : JSON.stringify(value)}
                  </span>
                </div>
              ))}
            </div>
          </details>
        </div>
      )}

      {hasWarnings && (
        <div className="border-t border-neutral-100 px-5 py-2.5">
          {result.warnings.map((w, i) => (
            <p key={i} className="text-[11px] text-neutral-400 leading-relaxed">
              {w}
            </p>
          ))}
        </div>
      )}
    </div>
  )
}
