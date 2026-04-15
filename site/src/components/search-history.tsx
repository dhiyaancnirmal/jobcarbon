"use client"

import { useMemo, useState } from "react"
import type { HistoryItem } from "@/lib/api"
import { HistoryCard } from "@/components/history-card"

export function SearchHistory({
  items,
  expandedId,
  onToggleExpand,
  onRecheck,
  onRemove,
  onClearAll,
}: {
  items: HistoryItem[]
  expandedId: string | null
  onToggleExpand: (id: string | null) => void
  onRecheck: (item: HistoryItem) => void
  onRemove: (id: string) => void
  onClearAll: () => void
}) {
  const [filter, setFilter] = useState("")

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
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="text-xs text-neutral-500">
            {items.length} {items.length === 1 ? "result" : "results"}
          </span>
          <button
            type="button"
            onClick={onClearAll}
            className="text-xs text-neutral-400 transition-colors hover:text-neutral-600"
          >
            Clear all
          </button>
        </div>
        <input
          type="text"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter by title, company…"
          className="h-8 w-56 rounded-md border border-neutral-200 bg-white px-3 text-xs text-neutral-700 outline-none transition-colors placeholder:text-neutral-400 focus:border-neutral-400"
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
              onRecheck={() => onRecheck(item)}
              onRemove={() => onRemove(item.id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
