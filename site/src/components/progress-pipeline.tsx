"use client"

import { AlertTriangle, Check, Loader2 } from "lucide-react"
import { getPlatformPresentation } from "@/lib/supported-platforms"

export type StageStatus = "running" | "ok" | "warn"

export type StageRow = {
  label: string
  status: StageStatus
  detail?: string
}

export function ProgressPipeline({
  platform,
  stages,
}: {
  platform: string | null
  stages: StageRow[]
}) {
  const platformUi =
    platform && platform !== "unknown" ? getPlatformPresentation(platform) : null

  return (
    <div className="flex flex-col gap-2 rounded-xl border border-neutral-200 bg-white px-3 py-2.5">
      <div className="flex items-center gap-2">
        <Loader2
          className="size-3.5 animate-spin text-neutral-400"
          strokeWidth={2}
          aria-hidden
        />
        <span className="text-[13px] font-medium text-neutral-700">
          Checking{platformUi ? ` \u00b7 ${platformUi.displayName}` : ""}
        </span>
      </div>
      {stages.length === 0 ? (
        <p className="text-[13px] text-neutral-400">
          Detecting platform and loading the page…
        </p>
      ) : (
        <ol className="flex flex-col gap-1">
          {stages.map((stage, i) => (
            <li
              key={`${stage.label}-${i}`}
              className="flex items-baseline gap-2.5 text-[13px]"
            >
              <span className="mt-0.5 inline-flex size-3.5 shrink-0 items-center justify-center self-start">
                <StageIcon status={stage.status} />
              </span>
              <div className="flex flex-1 flex-col gap-0.5">
                <span
                  className={
                    stage.status === "warn"
                      ? "text-neutral-500"
                      : "text-neutral-800"
                  }
                >
                  {stage.label}
                </span>
                {stage.status === "warn" && stage.detail && (
                  <span className="text-[11px] text-neutral-400">
                    {stage.detail}
                  </span>
                )}
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}

function StageIcon({ status }: { status: StageStatus }) {
  if (status === "running") {
    return (
      <Loader2
        className="size-3.5 animate-spin text-neutral-400"
        strokeWidth={2}
        aria-hidden
      />
    )
  }
  if (status === "ok") {
    return (
      <Check
        className="size-3.5 text-emerald-600"
        strokeWidth={2.5}
        aria-hidden
      />
    )
  }
  return (
    <AlertTriangle
      className="size-3.5 text-amber-500"
      strokeWidth={2}
      aria-hidden
    />
  )
}
