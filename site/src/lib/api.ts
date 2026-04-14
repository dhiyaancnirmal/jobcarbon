export type EstimateResult = {
  url: string
  normalized_url: string
  platform: string
  status: "success" | "blocked" | "no_date" | "unsupported" | "error"
  title: string | null
  company: string | null
  location: string | null
  employment_type: string | null
  likely_posted_date: string | null
  likely_age_days: number | null
  confidence: "high" | "medium" | "low" | "unknown"
  reposted_likely: boolean
  summary: string
  chosen_source: {
    date: string
    source: string
    field: string
    kind: string
    reliability: "high" | "medium" | "low"
    note?: string
  } | null
  all_dates: Array<{
    date: string
    source: string
    field: string
    kind: string
    reliability: "high" | "medium" | "low"
    note?: string
  }>
  hidden_insights: Record<string, unknown>
  warnings: string[]
}

export type ApiError = {
  error: {
    code: string
    message: string
  }
}

const API_BASE =
  process.env.NEXT_PUBLIC_JOBCARBON_API ??
  "https://api.howoldisthisjob.com"

export async function estimateJobAge(url: string): Promise<EstimateResult> {
  const endpoint = `${API_BASE}/api/v1/estimate?url=${encodeURIComponent(url)}`
  const response = await fetch(endpoint, { method: "GET" })
  const payload = await response.json()

  if (!response.ok) {
    const err = payload as ApiError
    throw new Error(err?.error?.message ?? `Request failed (${response.status})`)
  }

  return payload as EstimateResult
}
