"use client"

import { SUPPORTED_PLATFORMS } from "@/lib/supported-platforms"

function makeButtons(prefix: string) {
  return SUPPORTED_PLATFORMS.map((p, i) => (
    <a
      key={`${prefix}-${i}`}
      href={p.href}
      target="_blank"
      rel="noopener noreferrer"
      className={`gel-btn gel-btn--sm ${p.gelClass}`}
    >
      {p.displayName}
    </a>
  ))
}

export function PlatformCarousel() {
  return (
    <div className="carousel-wrapper">
      <div className="carousel-track carousel-track--animate">
        {makeButtons("a")}
        {makeButtons("b")}
      </div>
    </div>
  )
}
