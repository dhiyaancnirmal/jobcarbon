"use client"

import { SUPPORTED_PLATFORMS } from "@/lib/supported-platforms"

function makeButtons(prefix: string, clone = false) {
  return SUPPORTED_PLATFORMS.map((p, i) => (
    <a
      key={`${prefix}-${i}`}
      href={p.href}
      target="_blank"
      rel="noopener noreferrer"
      tabIndex={clone ? -1 : undefined}
      aria-hidden={clone ? "true" : undefined}
      className={`gel-btn gel-btn--sm ${p.gelClass} ${clone ? "pointer-events-none" : ""}`}
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
        <div aria-hidden="true" className="contents">
          {makeButtons("b", true)}
        </div>
      </div>
    </div>
  )
}
