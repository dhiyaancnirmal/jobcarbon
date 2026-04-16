"use client"

export function Logo({ size = 48 }: { size?: number }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 120 120"
      width={size}
      height={size}
    >
      <defs>
        <linearGradient id="whiteGel" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#ffffff" />
          <stop offset="100%" stopColor="#f0f0f0" />
        </linearGradient>
        <linearGradient id="blueGel" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#5bb4ff" />
          <stop offset="100%" stopColor="#257cff" />
        </linearGradient>
        <filter id="outerShadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="2" stdDeviation="2" floodColor="#000000" floodOpacity="0.1" />
        </filter>
        <clipPath id="calClip">
          <rect x="10" y="20" width="100" height="90" rx="8" ry="8" />
        </clipPath>
      </defs>
      <rect x="10" y="20" width="100" height="90" rx="8" ry="8" fill="#ffffff" filter="url(#outerShadow)" />
      <g clipPath="url(#calClip)">
        <rect x="10" y="20" width="100" height="90" fill="url(#whiteGel)" />
        <rect x="10" y="20" width="100" height="25" fill="url(#blueGel)" />
        <path d="M 10 20 L 110 20 L 110 22 L 10 22 Z" fill="rgba(255,255,255,0.4)" />
        <path d="M 10 20 L 12 20 L 12 45 L 10 45 Z" fill="rgba(255,255,255,0.2)" />
        <path d="M 10 108 L 110 108 L 110 110 L 10 110 Z" fill="rgba(0,0,0,0.05)" />
        <line x1="10" y1="45" x2="110" y2="45" stroke="#1e6add" strokeWidth="1" />
      </g>
      <rect x="10" y="20" width="100" height="90" rx="8" ry="8" fill="none" stroke="#d1d1d1" strokeWidth="1" />
      <path d="M 10 45 L 10 28 A 8 8 0 0 1 18 20 L 102 20 A 8 8 0 0 1 110 28 L 110 45" fill="none" stroke="#1e6add" strokeWidth="1" />
      <path d="M 12 28 A 6 6 0 0 1 18 22 L 102 22 A 6 6 0 0 1 108 28" fill="none" stroke="rgba(255,255,255,0.4)" strokeWidth="2" />
      <path d="M 12 102 A 6 6 0 0 0 18 108 L 102 108 A 6 6 0 0 0 108 102" fill="none" stroke="rgba(0,0,0,0.05)" strokeWidth="2" />
      <rect x="30" y="10" width="8" height="20" rx="4" ry="4" fill="#ffffff" stroke="#d1d1d1" strokeWidth="1" filter="url(#outerShadow)" />
      <rect x="82" y="10" width="8" height="20" rx="4" ry="4" fill="#ffffff" stroke="#d1d1d1" strokeWidth="1" filter="url(#outerShadow)" />
      <path d="M 32 14 A 2 2 0 0 1 36 14" fill="none" stroke="rgba(255,255,255,0.8)" strokeWidth="2" />
      <path d="M 84 14 A 2 2 0 0 1 88 14" fill="none" stroke="rgba(255,255,255,0.8)" strokeWidth="2" />
    </svg>
  )
}
