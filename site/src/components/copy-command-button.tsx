"use client"

import { Check, Copy } from "lucide-react"
import { useState } from "react"

export function CopyCommandButton({ command }: { command: string }) {
  const [copied, setCopied] = useState(false)

  async function onCopy() {
    try {
      await navigator.clipboard.writeText(command)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch {}
  }

  return (
    <button
      type="button"
      onClick={onCopy}
      className="gel-btn gel-btn--xs gel-btn--neutral shrink-0"
      aria-label={copied ? "Copied command" : "Copy command"}
      title={copied ? "Copied" : "Copy command"}
    >
      {copied ? (
        <Check className="size-3.5 text-emerald-600" strokeWidth={2.25} aria-hidden />
      ) : (
        <Copy className="size-3.5 text-neutral-400" strokeWidth={1.75} aria-hidden />
      )}
    </button>
  )
}
