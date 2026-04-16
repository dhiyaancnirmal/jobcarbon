"use client"

import type { HistoryItem } from "@/lib/api"
import { ResultCard } from "@/components/result-card"

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
          </div>
        </div>
        <span className="shrink-0 text-[11px] text-neutral-400">Expand</span>
      </button>
    )
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-end px-1">
        <button
          type="button"
          onClick={onToggle}
          className="text-[11px] text-neutral-400 transition-colors hover:text-neutral-600"
        >
          Collapse
        </button>
      </div>
      <ResultCard result={result} onRemove={onRemove} />
      <p className="truncate px-1 text-center text-[11px] text-neutral-400">
        {item.url}
      </p>
    </div>
  )
}
