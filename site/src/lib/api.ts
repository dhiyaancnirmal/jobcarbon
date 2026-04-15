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

export type PlatformCapability = {
  platform: string
  display_name: string
  supported: boolean
  integration: "direct" | "generic" | "blocked" | "unsupported"
  detection: string[]
  notes: string
}

export type PlatformsResponse = {
  platforms: PlatformCapability[]
  summary: {
    supported: number
    direct: number
    generic: number
    blocked: number
    unsupported: number
  }
}

export type ApiError = {
  error: {
    code: string
    message: string
  }
}

export type HistoryItem = {
  id: string
  created_at: string
  url: string
  result: EstimateResult
}

const API_BASE =
  process.env.NEXT_PUBLIC_JOBCARBON_API ??
  (process.env.NODE_ENV === "development"
    ? "http://localhost:8000"
    : "https://api.howoldisthisjob.com")

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

export async function fetchPlatforms(): Promise<PlatformsResponse> {
  const endpoint = `${API_BASE}/api/v1/platforms`
  const response = await fetch(endpoint, { method: "GET" })
  const payload = await response.json()

  if (!response.ok) {
    const err = payload as ApiError
    throw new Error(err?.error?.message ?? `Request failed (${response.status})`)
  }

  return payload as PlatformsResponse
}

async function parseApiResponse<T>(response: Response): Promise<T> {
  const payload = await response.json()

  if (!response.ok) {
    const err = payload as ApiError
    throw new Error(err?.error?.message ?? `Request failed (${response.status})`)
  }

  return payload as T
}

export async function fetchHistory(): Promise<HistoryItem[]> {
  const response = await fetch(`${API_BASE}/api/v1/history`, {
    method: "GET",
    credentials: "include",
  })
  const payload = await parseApiResponse<{ history: HistoryItem[] }>(response)
  return payload.history
}

export async function saveToHistory(
  url: string,
  result: EstimateResult,
): Promise<HistoryItem> {
  const response = await fetch(`${API_BASE}/api/v1/history`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ url, result }),
  })
  const payload = await parseApiResponse<{ item: HistoryItem }>(response)
  return payload.item
}

export async function deleteHistoryItem(id: string): Promise<void> {
  const response = await fetch(`${API_BASE}/api/v1/history/${encodeURIComponent(id)}`, {
    method: "DELETE",
    credentials: "include",
  })

  if (!response.ok && response.status !== 204) {
    const payload = await response.json()
    const err = payload as ApiError
    throw new Error(err?.error?.message ?? `Request failed (${response.status})`)
  }
}

export async function clearHistory(): Promise<void> {
  const response = await fetch(`${API_BASE}/api/v1/history`, {
    method: "DELETE",
    credentials: "include",
  })

  if (!response.ok && response.status !== 204) {
    const payload = await response.json()
    const err = payload as ApiError
    throw new Error(err?.error?.message ?? `Request failed (${response.status})`)
  }
}
