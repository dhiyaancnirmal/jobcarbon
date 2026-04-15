"use client"

export function Spinner({
  className,
}: {
  className?: string
}) {
  return (
    <span className={`inline-flex items-center gap-1 ${className ?? ""}`}>
      <span className="h-1.5 w-1.5 animate-[pulse_0.9s_ease-in-out_infinite] rounded-full bg-current [animation-delay:-0.3s]" />
      <span className="h-1.5 w-1.5 animate-[pulse_0.9s_ease-in-out_infinite] rounded-full bg-current [animation-delay:-0.15s]" />
      <span className="h-1.5 w-1.5 animate-[pulse_0.9s_ease-in-out_infinite] rounded-full bg-current" />
    </span>
  )
}
