"use client"

import { useMemo, useState } from "react"
import type { HistoryItem } from "@/lib/api"
import { HistoryCard } from "@/components/history-card"

export function SearchHistory({
  items,
  expandedId,
  onToggleExpand,
  onRemove,
  onClearAll,
}: {
  items: HistoryItem[]
  expandedId: string | null
  onToggleExpand: (id: string | null) => void
  onRemove: (id: string) => void
  onClearAll: () => void
}) {
  const [filter, setFilter] = useState("")
  const [confirmingClear, setConfirmingClear] = useState(false)

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase()
    if (!q) return items
    return items.filter((it) => {
      const r = it.result
      return (
        (r.title ?? "").toLowerCase().includes(q) ||
        (r.company ?? "").toLowerCase().includes(q) ||
        (r.platform ?? "").toLowerCase().includes(q) ||
        it.url.toLowerCase().includes(q)
      )
    })
  }, [items, filter])

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="text-xs text-neutral-500">
            {filtered.length === items.length
              ? `${items.length} ${items.length === 1 ? "result" : "results"}`
              : `${filtered.length} of ${items.length} results`}
          </span>
          {confirmingClear ? (
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-neutral-500">Clear all?</span>
              <button
                type="button"
                onClick={() => {
                  setConfirmingClear(false)
                  onClearAll()
                }}
                className="gel-btn gel-btn--sm gel-btn--destructive h-6 px-2.5 text-[11px]"
              >
                Yes
              </button>
              <button
                type="button"
                onClick={() => setConfirmingClear(false)}
                className="gel-btn gel-btn--sm gel-btn--neutral h-6 px-2.5 text-[11px]"
              >
                No
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setConfirmingClear(true)}
              className="text-xs text-neutral-400 transition-colors hover:text-neutral-600"
            >
              Clear all
            </button>
          )}
        </div>
        <input
          type="text"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter by title, company…"
          aria-label="Filter results"
          className="gel-input h-8 min-h-8 w-full min-w-0 rounded-md px-3 text-xs sm:w-56"
        />
      </div>

      {filtered.length === 0 ? (
        <p className="rounded-xl border border-dashed border-neutral-200 bg-white px-5 py-6 text-center text-xs text-neutral-400">
          No results match &ldquo;{filter}&rdquo;.
        </p>
      ) : (
        <div className="flex flex-col gap-2">
          {filtered.map((item) => (
            <HistoryCard
              key={item.id}
              item={item}
              expanded={item.id === expandedId}
              onToggle={() =>
                onToggleExpand(item.id === expandedId ? null : item.id)
              }
              onRemove={() => onRemove(item.id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
