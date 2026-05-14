"use client"

import type { HistoryItem } from "@/lib/api"
import { ResultCard } from "@/components/result-card"

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

function shortAge(days: number | null): string | null {
  if (days === null) return null
  if (days === 0) return "Today"
  if (days < 30) return `${days}d`
  const months = Math.floor(days / 30)
  if (months < 12) return `${months}mo`
  const years = Math.floor(days / 365)
  return `${years}y`
}

export function HistoryCard({
  item,
  expanded,
  onToggle,
  onRemove,
}: {
  item: HistoryItem
  expanded: boolean
  onToggle: () => void
  onRemove: () => void
}) {
  const { result } = item
  const title = result.title ?? "Unknown position"
  const company = result.company ?? ""
  const ageDays = localCalendarAgeDays(result.likely_posted_date) ?? result.likely_age_days
  const age = shortAge(ageDays)

  if (!expanded) {
    return (
      <button
        type="button"
        onClick={onToggle}
        className="interactive-card flex w-full items-center gap-3 rounded-xl border border-neutral-200 bg-white px-4 py-3 text-left dark:border-neutral-800 dark:bg-neutral-950"
      >
        <div className="flex min-w-0 flex-1 flex-col">
          <span className="truncate text-sm font-medium text-neutral-800 dark:text-neutral-100">{title}</span>
          {company && (
            <span className="truncate text-[11px] text-neutral-400 dark:text-neutral-500">
              {company}
            </span>
          )}
        </div>
        {age && (
          <span className="shrink-0 rounded-md border border-neutral-200 bg-neutral-50 px-2 py-0.5 text-[11px] font-medium tabular-nums text-neutral-700 dark:border-neutral-800 dark:bg-neutral-900 dark:text-neutral-200">
            {age}
          </span>
        )}
        <span className="shrink-0 text-[11px] text-neutral-400 dark:text-neutral-500">Expand</span>
      </button>
    )
  }

  return (
    <div className="motion-card-enter flex flex-col gap-2">
      <div className="flex items-center justify-end px-1">
        <button
          type="button"
          onClick={onToggle}
          className="text-[11px] text-neutral-400 transition-colors hover:text-neutral-600 dark:text-neutral-500 dark:hover:text-neutral-300"
        >
          Collapse
        </button>
      </div>
      <ResultCard result={result} onRemove={onRemove} />
      <p className="truncate px-1 text-center text-[11px] text-neutral-400 dark:text-neutral-500">
        {item.url}
      </p>
    </div>
  )
}
