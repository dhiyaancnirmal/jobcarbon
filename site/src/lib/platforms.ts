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
      "LinkedIn blocks automated access to their job pages, so we cannot extract posting dates or any job data.\n\nTip: if you see an \"Apply\" button (not \"Easy Apply\"), click it to get the company's own careers page URL — that will give much better results.",
    mode: "blocked",
    dismissLabel: "Got it",
  },
  indeed: {
    id: "indeed",
    title: "Indeed URL Detected",
    body:
      "Indeed blocks automated access to their job pages, so we cannot extract posting dates or any job data.\n\nTip: look for the original company careers page link on the Indeed listing — that will give much better results.",
    mode: "blocked",
    dismissLabel: "Got it",
  },
  google: {
    id: "google",
    title: "Google Careers Detected",
    body:
      "Google Careers pages do not contain posting dates or last-modified timestamps.\n\nWe can extract the job title and company name, but cannot determine when this job was posted.",
    mode: "warn",
    continueLabel: "Continue Anyway",
    dismissLabel: "Cancel",
  },
  clearcompany: {
    id: "clearcompany",
    title: "Unsupported ATS Detected",
    body:
      "This job is hosted on ClearCompany, an applicant tracking system that does not include posting dates in their pages.\n\nTip: try searching for this job title on the company's main careers page — other ATS platforms often include dates.",
    mode: "blocked",
    dismissLabel: "Got it",
  },
  ycombinator: {
    id: "ycombinator",
    title: "Y Combinator Job Board Detected",
    body:
      "Work at a Startup (workatastartup.com) does not include posting dates in their job listings. This is by design — the site intentionally omits dates.\n\nWe can try to extract the job title and company name, but cannot determine when this job was posted.",
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
