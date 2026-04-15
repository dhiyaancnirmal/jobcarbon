"use client"

import { useEffect } from "react"
import { INTERCEPTS, type InterceptPlatform } from "@/lib/platforms"

export function PlatformDialog({
  platform,
  onContinue,
  onCancel,
}: {
  platform: InterceptPlatform | null
  onContinue: () => void
  onCancel: () => void
}) {
  useEffect(() => {
    if (!platform) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel()
    }
    document.addEventListener("keydown", onKey)
    return () => document.removeEventListener("keydown", onKey)
  }, [platform, onCancel])

  if (!platform) return null
  const spec = INTERCEPTS[platform]

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-neutral-900/40 px-4"
      onClick={onCancel}
    >
      <div
        role="dialog"
        aria-modal="true"
        className="w-full max-w-md rounded-xl border border-neutral-200 bg-white p-5 shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-base font-semibold text-neutral-900">{spec.title}</h2>
        <p className="mt-2 whitespace-pre-line text-sm text-neutral-600 leading-relaxed">
          {spec.body}
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md border border-neutral-200 bg-white px-3 py-1.5 text-sm text-neutral-700 transition-colors hover:bg-neutral-50"
          >
            {spec.dismissLabel}
          </button>
          {spec.mode === "warn" && (
            <button
              type="button"
              onClick={onContinue}
              className="rounded-md bg-neutral-900 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-neutral-700"
            >
              {spec.continueLabel ?? "Continue"}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
