"use client"

const PLATFORMS = [
  {
    name: "Lever",
    gelClass: "gel-btn--lever",
    icon: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
        <rect x="3" y="3" width="7" height="7" rx="1.5" fill="currentColor" opacity="0.85"/>
        <rect x="14" y="3" width="7" height="7" rx="1.5" fill="currentColor" opacity="0.85"/>
        <rect x="3" y="14" width="7" height="7" rx="1.5" fill="currentColor" opacity="0.85"/>
        <rect x="14" y="14" width="7" height="7" rx="1.5" fill="currentColor" opacity="0.6"/>
      </svg>
    ),
  },
  {
    name: "Greenhouse",
    gelClass: "gel-btn--greenhouse",
    icon: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
        <path d="M12 2L3 7v10l9 5 9-5V7l-9-5zm0 2.5L18.5 7.5 12 10.5 5.5 7.5 12 4.5z" fill="currentColor" opacity="0.85"/>
      </svg>
    ),
  },
  {
    name: "Ashby",
    gelClass: "gel-btn--ashby",
    icon: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
        <path d="M12 2l2.9 6.3L22 9.3l-5 4.9 1.2 6.9L12 17.8l-6.2 3.3L7 14.2 2 9.3l7.1-1L12 2z" fill="currentColor" opacity="0.85"/>
      </svg>
    ),
  },
  {
    name: "SmartRecruiters",
    gelClass: "gel-btn--smartrecruiters",
    icon: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
        <path d="M12 2a10 10 0 100 20 10 10 0 000-20zm0 3a3 3 0 012.5 4.6L13 13h-2l-1.5-3.4A3 3 0 0112 5zm0 11a1.5 1.5 0 110-3 1.5 1.5 0 010 3z" fill="currentColor" opacity="0.85"/>
      </svg>
    ),
  },
]

function makeButtons(withLogos: boolean, prefix: string) {
  return PLATFORMS.map((p, i) => (
    <span key={`${prefix}-${i}`} className={`gel-btn gel-btn--sm ${p.gelClass}`}>
      {withLogos && p.icon}
      {p.name}
    </span>
  ))
}

export function PlatformCarousel({ withLogos = false }: { withLogos?: boolean }) {
  return (
    <div className="carousel-wrapper">
      <div className="carousel-track carousel-track--animate">
        {makeButtons(withLogos, "a")}
        {makeButtons(withLogos, "b")}
        {makeButtons(withLogos, "c")}
        {makeButtons(withLogos, "d")}
        {makeButtons(withLogos, "e")}
        {makeButtons(withLogos, "f")}
      </div>
    </div>
  )
}
