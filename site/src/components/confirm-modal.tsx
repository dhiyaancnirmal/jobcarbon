"use client"

import { useEffect } from "react"

export function ConfirmModal({
  open,
  title,
  description,
  confirmText = "Confirm",
  cancelText = "Cancel",
  destructive = false,
  onConfirm,
  onCancel,
}: {
  open: boolean
  title: string
  description: string
  confirmText?: string
  cancelText?: string
  destructive?: boolean
  onConfirm: () => void
  onCancel: () => void
}) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel()
    }
    document.addEventListener("keydown", onKey)
    return () => document.removeEventListener("keydown", onKey)
  }, [open, onCancel])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-neutral-900/40 px-4"
      onClick={onCancel}
    >
      <div
        role="dialog"
        aria-modal="true"
        className="w-full max-w-sm rounded-xl border border-neutral-200 bg-white p-5 shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-base font-semibold text-neutral-900">{title}</h2>
        <p className="mt-2 text-sm text-neutral-500">{description}</p>
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md border border-neutral-200 bg-white px-3 py-1.5 text-sm text-neutral-700 transition-colors hover:bg-neutral-50"
          >
            {cancelText}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className={`rounded-md px-3 py-1.5 text-sm font-medium text-white transition-colors ${
              destructive
                ? "bg-red-600 hover:bg-red-700"
                : "bg-neutral-900 hover:bg-neutral-700"
            }`}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  )
}
