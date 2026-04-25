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

export type BatchEstimateItem =
  | {
      url: string
      ok: true
      result: EstimateResult
    }
  | {
      url: string
      ok: false
      error: {
        code: string
        message: string
      }
    }

export type BatchEstimateResponse = {
  results: BatchEstimateItem[]
}

const DEFAULT_PROD_API_BASES = ["https://api.howoldisthisjob.com"]

const API_BASES = (() => {
  if (process.env.NODE_ENV === "development") {
    return ["http://localhost:8000"]
  }

  const configured = process.env.NEXT_PUBLIC_HOWOLDISTHISJOB_API?.trim()
  if (!configured) return DEFAULT_PROD_API_BASES

  return Array.from(new Set([...DEFAULT_PROD_API_BASES, configured]))
})()

function isRetryableApiStatus(status: number): boolean {
  return [502, 503, 504, 522, 523, 524, 530].includes(status)
}

async function fetchApi(path: string, init?: RequestInit): Promise<Response> {
  let lastError: unknown = null

  for (let index = 0; index < API_BASES.length; index += 1) {
    const base = API_BASES[index]

    try {
      const response = await fetch(`${base}${path}`, init)
      if (response.ok || !isRetryableApiStatus(response.status) || index === API_BASES.length - 1) {
        return response
      }
    } catch (error) {
      lastError = error
      if (index === API_BASES.length - 1) {
        throw error
      }
      continue
    }
  }

  throw lastError instanceof Error
    ? lastError
    : new Error("Could not reach the howoldisthisjob API.")
}

export async function estimateJobAge(url: string): Promise<EstimateResult> {
  const response = await fetchApi(`/api/v1/estimate?url=${encodeURIComponent(url)}`, {
    method: "GET",
  })
  const payload = await response.json()

  if (!response.ok) {
    const err = payload as ApiError
    throw new Error(err?.error?.message ?? `Request failed (${response.status})`)
  }

  return payload as EstimateResult
}

export type StreamEvent =
  | { type: "start"; url: string }
  | { type: "platform"; platform: string }
  | {
      type: "stage"
      label: string
      status: "start" | "ok" | "warn"
      detail?: string
    }
  | { type: "result"; result: EstimateResult }
  | { type: "error"; code: string; message: string }

export async function streamEstimateJobAge(
  url: string,
  onEvent: (event: StreamEvent) => void,
  options?: { signal?: AbortSignal },
): Promise<EstimateResult> {
  const response = await fetchApi(`/api/v1/estimate/stream?url=${encodeURIComponent(url)}`, {
    method: "GET",
    signal: options?.signal,
  })

  if (!response.ok || !response.body) {
    let message = `Stream request failed (${response.status})`
    try {
      const payload = (await response.json()) as ApiError
      if (payload?.error?.message) message = payload.error.message
    } catch {}
    throw new Error(message)
  }

  const reader = response.body
    .pipeThrough(new TextDecoderStream())
    .getReader()

  let buffer = ""
  let result: EstimateResult | null = null

  try {
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += value
      let newlineIdx = buffer.indexOf("\n")
      while (newlineIdx >= 0) {
        const line = buffer.slice(0, newlineIdx).trim()
        buffer = buffer.slice(newlineIdx + 1)
        if (line) {
          let event: StreamEvent
          try {
            event = JSON.parse(line) as StreamEvent
          } catch {
            newlineIdx = buffer.indexOf("\n")
            continue
          }
          onEvent(event)
          if (event.type === "result") result = event.result
          if (event.type === "error") throw new Error(event.message)
        }
        newlineIdx = buffer.indexOf("\n")
      }
    }
  } finally {
    try {
      reader.releaseLock()
    } catch {}
  }

  if (!result) {
    throw new Error("Stream ended without a result event.")
  }
  return result
}

export async function fetchPlatforms(): Promise<PlatformsResponse> {
  const response = await fetchApi("/api/v1/platforms", { method: "GET" })
  const payload = await response.json()

  if (!response.ok) {
    const err = payload as ApiError
    throw new Error(err?.error?.message ?? `Request failed (${response.status})`)
  }

  return payload as PlatformsResponse
}

export async function batchEstimateJobAge(
  urls: string[],
): Promise<BatchEstimateResponse> {
  const response = await fetchApi("/api/v1/batch-estimate", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ urls }),
  })

  return parseApiResponse<BatchEstimateResponse>(response)
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
  const response = await fetchApi("/api/v1/history", {
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
  const response = await fetchApi("/api/v1/history", {
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
  const response = await fetchApi(`/api/v1/history/${encodeURIComponent(id)}`, {
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
  const response = await fetchApi("/api/v1/history", {
    method: "DELETE",
    credentials: "include",
  })

  if (!response.ok && response.status !== 204) {
    const payload = await response.json()
    const err = payload as ApiError
    throw new Error(err?.error?.message ?? `Request failed (${response.status})`)
  }
}
