"use client"

import type { HistoryItem } from "@/lib/api"
import { ResultCard } from "@/components/result-card"

function formatRelative(iso: string): string {
  const then = new Date(iso).getTime()
  const now = Date.now()
  const diff = Math.max(0, now - then)
  const s = Math.floor(diff / 1000)
  if (s < 60) return "just now"
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  const d = Math.floor(h / 24)
  if (d < 7) return `${d}d ago`
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" })
}

export function HistoryCard({
  item,
  expanded,
  onToggle,
  onRecheck,
  onRemove,
}: {
  item: HistoryItem
  expanded: boolean
  onToggle: () => void
  onRecheck: () => void
  onRemove: () => void
}) {
  const { result } = item
  const title = result.title ?? "Unknown position"
  const company = result.company ?? ""
  const checked = formatRelative(item.created_at)

  if (!expanded) {
    return (
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between gap-3 rounded-xl border border-neutral-200 bg-white px-4 py-3 text-left transition-colors hover:bg-neutral-50"
      >
        <div className="flex min-w-0 flex-col">
          <span className="truncate text-sm font-medium text-neutral-800">{title}</span>
          <div className="flex items-center gap-2 text-[11px] text-neutral-400">
            {company && <span className="truncate">{company}</span>}
            {company && <span>·</span>}
            <span>Checked {checked}</span>
          </div>
        </div>
        <span className="shrink-0 text-[11px] text-neutral-400">Expand</span>
      </button>
    )
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between px-1">
        <span className="text-[11px] text-neutral-400">Checked {checked}</span>
        <button
          type="button"
          onClick={onToggle}
          className="text-[11px] text-neutral-400 transition-colors hover:text-neutral-600"
        >
          Collapse
        </button>
      </div>
      <ResultCard result={result} onRecheck={onRecheck} onRemove={onRemove} />
      <p className="truncate px-1 text-[11px] text-neutral-400">{item.url}</p>
    </div>
  )
}
