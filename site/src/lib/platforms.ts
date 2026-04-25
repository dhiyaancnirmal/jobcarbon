export type InterceptPlatform =
  | "linkedin"
  | "indeed"
  | "google"
  | "clearcompany"
  | "ycombinator"

export type InterceptSpec = {
  id: InterceptPlatform
  title: string
  body: string
  mode: "blocked" | "warn"
  continueLabel?: string
  dismissLabel: string
}

export const INTERCEPTS: Record<InterceptPlatform, InterceptSpec> = {
  linkedin: {
    id: "linkedin",
    title: "LinkedIn URL Detected",
    body:
      "LinkedIn blocks automated access to direct job-page lookups.\n\nTip: if you see an \"Apply\" button (not \"Easy Apply\"), use the employer careers URL instead. The Chrome extension can also recover source ATS links from some LinkedIn pages when the page exposes them locally.",
    mode: "blocked",
    dismissLabel: "Got it",
  },
  indeed: {
    id: "indeed",
    title: "Indeed URL Detected",
    body:
      "Indeed blocks automated access to direct job-page lookups.\n\nTip: use the original company careers URL instead. The Chrome extension can also recover source ATS links from some Indeed pages when the page exposes them locally.",
    mode: "blocked",
    dismissLabel: "Got it",
  },
  google: {
    id: "google",
    title: "Google Careers Detected",
    body:
      "Google Careers pages do not contain reliable posting dates.\n\nIf the page exposes the original employer apply URL, the Chrome extension can recover that source link and run the normal ATS lookup there.",
    mode: "warn",
    continueLabel: "Continue Anyway",
    dismissLabel: "Cancel",
  },
  clearcompany: {
    id: "clearcompany",
    title: "Unsupported Platform Detected",
    body:
      "This job is hosted on ClearCompany, a platform that does not include posting dates in their pages.\n\nTip: try searching for this job title on the company's main careers page. Other platforms often include dates.",
    mode: "blocked",
    dismissLabel: "Got it",
  },
  ycombinator: {
    id: "ycombinator",
    title: "Y Combinator Job Board Detected",
    body:
      "Work at a Startup (workatastartup.com) does not include posting dates in their job listings. This is by design; the site intentionally omits dates.\n\nWe can try to extract the job title and company name, but cannot determine when this job was posted.",
    mode: "warn",
    continueLabel: "Continue Anyway",
    dismissLabel: "Cancel",
  },
}

export function checkIntercept(url: string): InterceptPlatform | null {
  const u = url.toLowerCase()
  if (/linkedin\.com\/jobs/.test(u)) return "linkedin"
  if (/(?:^|\/\/)(?:[a-z0-9-]+\.)?indeed\.[a-z.]+\//.test(u)) return "indeed"
  if (/careers\.google\.com/.test(u)) return "google"
  if (/hrmdirect\.com|clearcompany\.com/.test(u)) return "clearcompany"
  if (/workatastartup\.com|ycombinator\.com\/jobs/.test(u)) return "ycombinator"
  return null
}
