"use client"

import { Check, Copy, Trash2 } from "lucide-react"
import { useState } from "react"
import type { EstimateResult } from "@/lib/api"
import { getPlatformPresentation } from "@/lib/supported-platforms"

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

const reliabilityDot: Record<string, string> = {
  high: "gel-dot--high",
  medium: "gel-dot--medium",
  low: "gel-dot--low",
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
      lines.push(`  ${d.date} - ${kindLabel[d.kind] ?? d.kind} from ${d.source}${d.field ? "." + d.field : ""}`)
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
  lines.push(`Checked via howoldisthisjob.com - ${result.url}`)
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
      className="gel-btn gel-btn--xs gel-btn--neutral"
      aria-label={copied ? "Copied to clipboard" : "Copy result to clipboard"}
      title={copied ? "Copied" : "Copy"}
    >
      {copied ? (
        <Check className="size-3.5 text-emerald-600" strokeWidth={2.25} aria-hidden />
      ) : (
        <Copy className="size-3.5 text-neutral-400" strokeWidth={1.75} aria-hidden />
      )}
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
          <span className="text-sm font-medium text-amber-800 dark:text-amber-200">Platform blocks automated access</span>
        </div>
        <p className="text-xs text-amber-700 leading-relaxed dark:text-amber-300">
          {`${result.platform} blocks automated access. Try the original company careers page URL instead.`}
        </p>
      </div>
    )
  }

  if (result.status === "unsupported") {
    return (
      <div className="flex flex-col gap-2 rounded-xl border border-neutral-200 bg-neutral-50 px-5 py-4 dark:border-neutral-800 dark:bg-neutral-950">
        <div className="flex items-center gap-2">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-neutral-500">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="16" x2="12" y2="12" />
            <line x1="12" y1="8" x2="12.01" y2="8" />
          </svg>
          <span className="text-sm font-medium text-neutral-700 dark:text-neutral-100">Platform not supported</span>
        </div>
        <p className="text-xs text-neutral-500 leading-relaxed dark:text-neutral-400">
          {`${result.platform} does not expose reliable posting dates.`}
        </p>
      </div>
    )
  }

  if (result.status === "no_date") {
    return (
      <div className="flex flex-col gap-2 rounded-xl border border-neutral-200 bg-white px-5 py-4 dark:border-neutral-800 dark:bg-neutral-950">
        <div className="flex items-center gap-2">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-neutral-400">
            <circle cx="12" cy="12" r="10" />
            <polyline points="12 6 12 12 16 14" />
          </svg>
          <span className="text-sm font-medium text-neutral-700 dark:text-neutral-100">No posting date found</span>
        </div>
        <p className="text-xs text-neutral-500 leading-relaxed dark:text-neutral-400">
          We checked structured data, platform APIs, and archives but couldn&apos;t find a reliable posting date for this listing.
        </p>
      </div>
    )
  }

  return null
}

export function ResultCard({
  result,
  onRemove,
}: {
  result: EstimateResult
  onRemove?: () => void
}) {
  const [evidenceExpanded, setEvidenceExpanded] = useState(false)
  const [insightsExpanded, setInsightsExpanded] = useState(false)

  if (result.status !== "success") {
    return (
      <div className="flex flex-col gap-2">
        <StatusMessage result={result} />
        {onRemove && (
          <div className="flex items-center gap-2 px-1">
            <button
              type="button"
              onClick={onRemove}
              className="gel-btn gel-btn--sm gel-btn--neutral"
            >
              Remove
            </button>
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
  const copyText = buildCopyText(result)
  const platformUi = getPlatformPresentation(result.platform)

  return (
    <div className="flex flex-col overflow-hidden rounded-xl border border-neutral-200 bg-white dark:border-neutral-800 dark:bg-neutral-950">
      {/* Header — primary content, most breathing room */}
      <div className="flex items-start justify-between gap-3 px-5 pb-4 pt-5">
        <div className="flex min-w-0 flex-col gap-1">
          <span className="text-xl font-semibold text-neutral-900 text-balance dark:text-neutral-50">
            {formatAge(displayAgeDays)}
          </span>
          {dateStr && (
            <span className="text-xs text-neutral-500 dark:text-neutral-400">Posted {dateStr}</span>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <CopyButton text={copyText} />
          {onRemove && (
            <button
              type="button"
              onClick={onRemove}
              className="gel-btn gel-btn--xs gel-btn--neutral"
              aria-label="Remove from history"
              title="Remove"
            >
              <Trash2 className="size-3.5 text-neutral-400" strokeWidth={1.75} aria-hidden />
            </button>
          )}
        </div>
      </div>

      {result.reposted_likely && (
        <div className="flex items-center gap-2 border-t border-amber-100 bg-amber-50/60 px-5 py-2.5 dark:border-amber-950 dark:bg-amber-950/40">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="shrink-0 text-amber-600">
            <polyline points="23 4 23 10 17 10" />
            <polyline points="1 20 1 14 7 14" />
            <path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15" />
          </svg>
          <span className="text-[11px] font-medium text-amber-700 dark:text-amber-300">
            Likely reposted - original listing may be older than shown
          </span>
        </div>
      )}

      {/* Job meta — secondary content */}
      {hasMeta && (
        <div className="flex flex-col gap-1 border-t border-neutral-100 px-5 py-4 dark:border-neutral-900">
          {result.title && (
            <span className="text-sm font-medium text-neutral-800 text-balance dark:text-neutral-100">{result.title}</span>
          )}
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            {result.company && (
              <span className="text-xs text-neutral-600 dark:text-neutral-300">{result.company}</span>
            )}
            {result.location && (
              <span className="text-xs text-neutral-500 dark:text-neutral-400">{result.location}</span>
            )}
            {result.employment_type && (
              <span className="text-xs text-neutral-500 dark:text-neutral-400">{result.employment_type}</span>
            )}
          </div>
        </div>
      )}

      {/* Platform / source — compact utility row */}
      <div className="flex flex-wrap items-center gap-2 border-t border-neutral-100 px-5 py-3 dark:border-neutral-900">
        {platformUi.href ? (
          <a
            href={platformUi.href}
            target="_blank"
            rel="noopener noreferrer"
            className={`gel-btn gel-btn--sm ${platformUi.gelClass} no-underline`}
          >
            {platformUi.displayName}
          </a>
        ) : (
          <span className={`gel-btn gel-btn--sm ${platformUi.gelClass} pointer-events-none`}>
            {platformUi.displayName}
          </span>
        )}
        {result.chosen_source && (
          <>
            <span className="text-[11px] text-neutral-500 dark:text-neutral-400">
              via {result.chosen_source.source}
              {result.chosen_source.field && `.${result.chosen_source.field}`}
            </span>
            <span
              className={`inline-block gel-dot ${reliabilityDot[result.chosen_source.reliability]}`}
            />
          </>
        )}
      </div>

      {/* Collapsible sections — compact toggle rows */}
      {(result.all_dates?.length ?? 0) > 0 && (
        <div className="border-t border-neutral-100 dark:border-neutral-900">
          <button
            type="button"
            onClick={() => setEvidenceExpanded((open) => !open)}
            className="flex w-full items-center justify-between px-5 py-2.5 text-left text-[11px] font-medium text-neutral-500 transition-colors hover:text-neutral-700 dark:text-neutral-400 dark:hover:text-neutral-200"
          >
            <span>
              Evidence ({result.all_dates!.length} date
              {result.all_dates!.length !== 1 ? "s" : ""} found)
            </span>
            <span className="text-neutral-500 dark:text-neutral-400">{evidenceExpanded ? "Hide" : "Show"}</span>
          </button>
          {evidenceExpanded && (
            <div className="flex flex-col gap-3 px-5 pb-4 pt-1">
              {result.all_dates!.map((item, i) => (
                <div
                  key={i}
                  className="flex items-start gap-3 text-[11px]"
                >
                  <span className="mt-0.5 flex size-4 shrink-0 items-center justify-center">
                    <span
                      className={`inline-block gel-dot ${reliabilityDot[item.reliability]}`}
                    />
                  </span>
                  <div className="flex flex-1 flex-col gap-0.5">
                    <div className="flex items-baseline gap-2">
                      <span className="font-mono tabular-nums text-neutral-700 dark:text-neutral-200">{item.date}</span>
                      <span className="text-neutral-500 dark:text-neutral-400">
                        {kindLabel[item.kind] ?? item.kind}
                      </span>
                    </div>
                    <span className="text-neutral-500 dark:text-neutral-400">
                      {item.source}
                      {item.field ? `.${item.field}` : ""}
                    </span>
                    {item.note && (
                      <span className="text-neutral-500 italic text-pretty dark:text-neutral-400">{item.note}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {hasInsights && (
        <div className="border-t border-neutral-100 dark:border-neutral-900">
          <button
            type="button"
            onClick={() => setInsightsExpanded((open) => !open)}
            className="flex w-full items-center justify-between px-5 py-2.5 text-left text-[11px] font-medium text-neutral-500 transition-colors hover:text-neutral-700 dark:text-neutral-400 dark:hover:text-neutral-200"
          >
            <span>
              Hidden insights ({Object.keys(result.hidden_insights ?? {}).length})
            </span>
            <span className="text-neutral-500 dark:text-neutral-400">{insightsExpanded ? "Hide" : "Show"}</span>
          </button>
          {insightsExpanded && (
            <div className="flex flex-col gap-3 px-5 pb-4 pt-1">
              {Object.entries(result.hidden_insights ?? {}).map(([key, value]) => (
                <div
                  key={key}
                  className="flex items-baseline gap-2 text-[11px]"
                >
                  <span className="shrink-0 text-neutral-500 dark:text-neutral-400">{key}</span>
                  <span className="truncate font-mono text-neutral-700 dark:text-neutral-200">
                    {typeof value === "string" ? value : JSON.stringify(value)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
