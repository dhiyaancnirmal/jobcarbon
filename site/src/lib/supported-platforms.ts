/**
 * Single source for supported hiring platforms: display names, gel button styles, and marketing links.
 * API `platform` values are matched case-insensitively after normalizing spaces/hyphens.
 */

export type SupportedPlatform = {
  /** Normalized key: lowercase, no spaces or punctuation (e.g. "ashby", "oraclehcm") */
  slug: string
  displayName: string
  gelClass: string
  href: string | null
}

export const SUPPORTED_PLATFORMS: SupportedPlatform[] = [
  { slug: "lever", displayName: "Lever", gelClass: "gel-btn--lever", href: "https://www.lever.co" },
  { slug: "greenhouse", displayName: "Greenhouse", gelClass: "gel-btn--greenhouse", href: "https://www.greenhouse.io" },
  { slug: "ashby", displayName: "Ashby", gelClass: "gel-btn--ashby", href: "https://www.ashbyhq.com" },
  { slug: "smartrecruiters", displayName: "SmartRecruiters", gelClass: "gel-btn--smartrecruiters", href: "https://www.smartrecruiters.com" },
  { slug: "dayforce", displayName: "Dayforce", gelClass: "gel-btn--dayforce", href: "https://www.dayforce.com" },
  { slug: "pageup", displayName: "PageUp", gelClass: "gel-btn--pageup", href: "https://www.pageuppeople.com" },
  { slug: "workable", displayName: "Workable", gelClass: "gel-btn--workable", href: "https://www.workable.com" },
  { slug: "workday", displayName: "Workday", gelClass: "gel-btn--workday", href: "https://www.workday.com" },
  { slug: "ukgpro", displayName: "UKG Pro", gelClass: "gel-btn--ukg-pro", href: "https://www.ukg.com" },
  { slug: "bamboohr", displayName: "BambooHR", gelClass: "gel-btn--bamboohr", href: "https://www.bamboohr.com" },
  { slug: "rippling", displayName: "Rippling", gelClass: "gel-btn--rippling", href: "https://www.rippling.com" },
  { slug: "icims", displayName: "iCIMS", gelClass: "gel-btn--icims", href: "https://www.icims.com" },
  { slug: "oraclehcm", displayName: "Oracle HCM", gelClass: "gel-btn--oracle-hcm", href: "https://www.oracle.com/human-capital-management" },
  { slug: "jobvite", displayName: "Jobvite", gelClass: "gel-btn--jobvite", href: "https://www.jobvite.com" },
  { slug: "brassring", displayName: "Brassring", gelClass: "gel-btn--brassring", href: "https://www.ibm.com/products/brassring" },
  { slug: "successfactors", displayName: "SuccessFactors", gelClass: "gel-btn--successfactors", href: "https://www.successfactors.com" },
  { slug: "taleo", displayName: "Taleo", gelClass: "gel-btn--taleo", href: "https://www.oracle.com/human-capital-management/taleo" },
  { slug: "avature", displayName: "Avature", gelClass: "gel-btn--avature", href: "https://www.avature.net" },
  { slug: "gem", displayName: "Gem", gelClass: "gel-btn--gem", href: "https://www.gem.com" },
  { slug: "teamtailor", displayName: "Teamtailor", gelClass: "gel-btn--teamtailor", href: "https://www.teamtailor.com" },
  { slug: "recruitee", displayName: "Recruitee", gelClass: "gel-btn--recruitee", href: "https://www.recruitee.com" },
  { slug: "personio", displayName: "Personio", gelClass: "gel-btn--personio", href: "https://www.personio.com" },
  { slug: "breezyhr", displayName: "Breezy HR", gelClass: "gel-btn--breezy", href: "https://breezy.hr" },
  { slug: "jazzhr", displayName: "JazzHR", gelClass: "gel-btn--jazzhr", href: "https://www.jazzhr.com" },
  { slug: "dover", displayName: "Dover", gelClass: "gel-btn--dover", href: "https://www.dover.io" },
  { slug: "adp", displayName: "ADP", gelClass: "gel-btn--adp", href: "https://www.adp.com" },
  { slug: "paycor", displayName: "Paycor", gelClass: "gel-btn--paycor", href: "https://www.paycor.com" },
]

const PLATFORM_BY_SLUG = new Map(SUPPORTED_PLATFORMS.map((p) => [p.slug, p]))

/** Detector / API may use a shorter slug than our canonical key */
const PLATFORM_ALIASES: Record<string, string> = {
  breezy: "breezyhr",
  ukg_pro: "ukgpro",
}
for (const [alias, canonical] of Object.entries(PLATFORM_ALIASES)) {
  const target = PLATFORM_BY_SLUG.get(canonical)
  if (target) PLATFORM_BY_SLUG.set(alias, target)
}

function normalizePlatformKey(raw: string): string {
  return raw
    .trim()
    .toLowerCase()
    .replace(/[\s_]+/g, "")
    .replace(/[^a-z0-9]/g, "")
}

function titleCaseFallback(raw: string): string {
  const t = raw.trim()
  if (!t) return "Unknown"
  return t
    .split(/[\s_-]+/)
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(" ")
}

export type PlatformPresentation = {
  displayName: string
  gelClass: string
  /** Vendor homepage when platform is in the supported list */
  href: string | null
}

/**
 * Maps API/platform detector strings to carousel-style label + gel class.
 * Unknown platforms get neutral styling and a readable title-cased label.
 */
export function getPlatformPresentation(platform: string): PlatformPresentation {
  const key = normalizePlatformKey(platform)
  if (key === "custombackend") {
    return {
      displayName: "Employer site",
      gelClass: "gel-btn--neutral",
      href: null,
    }
  }
  const found = PLATFORM_BY_SLUG.get(key)
  if (found) {
    return { displayName: found.displayName, gelClass: found.gelClass, href: found.href }
  }
  return {
    displayName: titleCaseFallback(platform),
    gelClass: "gel-btn--neutral",
    href: null,
  }
}
