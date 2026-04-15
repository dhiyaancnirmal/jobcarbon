"use client"

import { useState } from "react"
import type { EstimateResult } from "@/lib/api"

function localCalendarAgeDays(iso: string | null): number | null {
  if (!iso) return null
  const [year, month, day] = iso.split("-").map(Number)
  if (!year || !month || !day) return null
  const today = new Date()
  const localToday = new Date(today.getFullYear(), today.getMonth(), today.getDate())
  const postedDay = new Date(year, month - 1, day)
  const millisPerDay = 24 * 60 * 60 * 1000
  return Math.floor((localToday.getTime() - postedDay.getTime()) / millisPerDay)
}

function formatAge(days: number | null): string {
  if (days === null) return "Unknown"
  if (days === 0) return "Today"
  if (days === 1) return "1 day old"
  if (days < 30) return `${days} days old`
  const months = Math.floor(days / 30)
  if (months < 12) return months === 1 ? "~1 month old" : `~${months} months old`
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

function buildCopyText(result: EstimateResult): string {
  const lines: string[] = []
  if (result.title) lines.push(result.title)
  if (result.company) lines.push(`at ${result.company}`)
  const date = formatDate(result.likely_posted_date)
  const ageDays = localCalendarAgeDays(result.likely_posted_date) ?? result.likely_age_days
  if (date) lines.push(`Posted ${date} (${formatAge(ageDays)})`)
  if (result.chosen_source) {
    lines.push(
      `Source: ${result.chosen_source.source}${
        result.chosen_source.field ? "." + result.chosen_source.field : ""
      } (${result.chosen_source.reliability} reliability)`,
    )
  }
  if ((result.all_dates?.length ?? 0) > 1) {
    lines.push("")
    lines.push("All detected dates:")
    for (const d of result.all_dates ?? []) {
      lines.push(`  ${d.date} — ${kindLabel[d.kind] ?? d.kind} from ${d.source}${d.field ? "." + d.field : ""}`)
    }
  }
  const insights = Object.entries(result.hidden_insights ?? {})
  if (insights.length > 0) {
    lines.push("")
    lines.push("Hidden insights:")
    for (const [k, v] of insights) {
      lines.push(`  ${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`)
    }
  }
  lines.push("")
  lines.push(`Checked via howoldisthisjob.com — ${result.url}`)
  return lines.join("\n")
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  async function onCopy() {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {}
  }
  return (
    <button
      type="button"
      onClick={onCopy}
      className="rounded-md border border-neutral-200 bg-white px-2 py-1 text-[11px] font-medium text-neutral-600 transition-colors hover:bg-neutral-50"
    >
      {copied ? "Copied" : "Copy"}
    </button>
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
          {result.warnings?.[0] ?? `${result.platform} blocks automated access. Try the original company careers page URL instead.`}
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
          {result.warnings?.[0] ?? `${result.platform} does not expose reliable posting dates.`}
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
        {(result.warnings?.length ?? 0) > 0 && (
          <div className="mt-1 flex flex-col gap-1">
            {result.warnings!.map((w, i) => (
              <p key={i} className="text-[11px] text-neutral-400">
                {w}
              </p>
            ))}
          </div>
        )}
      </div>
    )
  }

  return null
}

export function ResultCard({
  result,
  onRecheck,
  onRemove,
}: {
  result: EstimateResult
  onRecheck?: () => void
  onRemove?: () => void
}) {
  if (result.status !== "success") {
    return (
      <div className="flex flex-col gap-2">
        <StatusMessage result={result} />
        {(onRecheck || onRemove) && (
          <div className="flex items-center gap-2 px-1">
            {onRecheck && (
              <button
                type="button"
                onClick={onRecheck}
                className="rounded-md border border-neutral-200 bg-white px-2 py-1 text-[11px] font-medium text-neutral-600 transition-colors hover:bg-neutral-50"
              >
                Check again
              </button>
            )}
            {onRemove && (
              <button
                type="button"
                onClick={onRemove}
                className="rounded-md border border-neutral-200 bg-white px-2 py-1 text-[11px] font-medium text-neutral-500 transition-colors hover:bg-neutral-50"
              >
                Remove
              </button>
            )}
          </div>
        )}
      </div>
    )
  }

  const dateStr = formatDate(result.likely_posted_date)
  const displayAgeDays =
    localCalendarAgeDays(result.likely_posted_date) ?? result.likely_age_days
  const hasMeta =
    result.title || result.company || result.location || result.employment_type
  const hasInsights = Object.keys(result.hidden_insights ?? {}).length > 0
  const hasWarnings = (result.warnings?.length ?? 0) > 0
  const copyText = buildCopyText(result)

  return (
    <div className="flex flex-col rounded-xl border border-neutral-200 bg-white overflow-hidden">
      <div className="flex items-start justify-between px-5 py-4">
        <div className="flex flex-col gap-1">
          <span className="text-xl font-semibold text-neutral-900">
            {formatAge(displayAgeDays)}
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
          <span className="text-[11px] font-medium text-amber-700">
            Likely reposted — original listing may be older than shown
          </span>
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
            <span
              className={`inline-block h-1.5 w-1.5 rounded-full ${reliabilityDot[result.chosen_source.reliability]}`}
            />
          </>
        )}
      </div>

      {(result.all_dates?.length ?? 0) > 0 && (
        <div className="border-t border-neutral-100">
          <details>
            <summary className="cursor-pointer px-5 py-2.5 text-[11px] font-medium text-neutral-400 transition-colors hover:text-neutral-600">
              Evidence ({result.all_dates!.length} date
              {result.all_dates!.length !== 1 ? "s" : ""} found)
            </summary>
            <div className="border-t border-neutral-100">
              {result.all_dates!.map((item, i) => (
                <div
                  key={i}
                  className="flex items-start gap-3 px-5 py-2 text-[11px] border-b border-neutral-50 last:border-b-0"
                >
                  <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center">
                    <span
                      className={`inline-block h-1.5 w-1.5 rounded-full ${reliabilityDot[item.reliability]}`}
                    />
                  </span>
                  <div className="flex flex-1 flex-col gap-0.5">
                    <div className="flex items-baseline gap-2">
                      <span className="font-mono text-neutral-700">{item.date}</span>
                      <span className="text-neutral-400">
                        {kindLabel[item.kind] ?? item.kind}
                      </span>
                    </div>
                    <span className="text-neutral-400">
                      {item.source}
                      {item.field ? `.${item.field}` : ""}
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
              Hidden insights ({Object.keys(result.hidden_insights ?? {}).length})
            </summary>
            <div className="border-t border-neutral-100">
              {Object.entries(result.hidden_insights ?? {}).map(([key, value]) => (
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
          {result.warnings!.map((w, i) => (
            <p key={i} className="text-[11px] text-neutral-400 leading-relaxed">
              {w}
            </p>
          ))}
        </div>
      )}

      <div className="flex items-center justify-end gap-2 border-t border-neutral-100 bg-neutral-50/40 px-5 py-2.5">
        <CopyButton text={copyText} />
        {onRecheck && (
          <button
            type="button"
            onClick={onRecheck}
            className="rounded-md border border-neutral-200 bg-white px-2 py-1 text-[11px] font-medium text-neutral-600 transition-colors hover:bg-neutral-50"
          >
            Check again
          </button>
        )}
        {onRemove && (
          <button
            type="button"
            onClick={onRemove}
            className="rounded-md border border-neutral-200 bg-white px-2 py-1 text-[11px] font-medium text-neutral-500 transition-colors hover:bg-neutral-50"
          >
            Remove
          </button>
        )}
      </div>
    </div>
  )
}
