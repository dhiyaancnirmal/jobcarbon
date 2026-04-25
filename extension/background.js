const API_BASE = "https://api.howoldisthisjob.com";
const REQUEST_TIMEOUT_BASE_MS = 20000;
const REQUEST_TIMEOUT_PER_URL_MS = 9000;
const REQUEST_TIMEOUT_MAX_MS = 120000;
const RESULT_CACHE_TTL_MS = 10 * 60 * 1000;
const RESULT_CACHE = new Map();

function requestTimeoutMs(urlCount) {
  const dynamicTimeout =
    REQUEST_TIMEOUT_BASE_MS + REQUEST_TIMEOUT_PER_URL_MS * Math.max(1, urlCount);
  return Math.min(dynamicTimeout, REQUEST_TIMEOUT_MAX_MS);
}

function cachedResult(url) {
  const entry = RESULT_CACHE.get(url);
  if (!entry) {
    return null;
  }
  if (entry.expiresAt <= Date.now()) {
    RESULT_CACHE.delete(url);
    return null;
  }
  return entry.item;
}

function storeResult(item) {
  if (!item?.url || item.ok !== true) {
    return;
  }
  RESULT_CACHE.set(item.url, {
    item,
    expiresAt: Date.now() + RESULT_CACHE_TTL_MS,
  });
}

function mergeResults(urls, fetchedResults) {
  const fetchedByUrl = new Map();
  for (const item of fetchedResults) {
    if (!item?.url) continue;
    fetchedByUrl.set(item.url, item);
    storeResult(item);
  }

  return urls.map((url) => {
    const cached = cachedResult(url);
    if (cached) {
      return cached;
    }
    return (
      fetchedByUrl.get(url) || {
        url,
        ok: false,
        error: {
          code: "missing_result",
          message: "Batch lookup did not return a result for this URL.",
        },
      }
    );
  });
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type !== "howoldisthisjob:batch-estimate") {
    return undefined;
  }

  (async () => {
    try {
      const urls = Array.isArray(message.urls) ? message.urls : [];
      if (urls.length === 0) {
        sendResponse({ ok: true, results: [] });
        return;
      }

      const uncachedUrls = urls.filter((url) => !cachedResult(url));
      if (uncachedUrls.length === 0) {
        sendResponse({
          ok: true,
          results: mergeResults(urls, []),
        });
        return;
      }

      const controller = new AbortController();
      const timeoutMs = requestTimeoutMs(uncachedUrls.length);
      const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
      const response = await fetch(`${API_BASE}/api/v1/batch-estimate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ urls: uncachedUrls }),
        signal: controller.signal,
      });
      clearTimeout(timeoutId);

      const raw = await response.text();
      let payload = null;
      try {
        payload = raw ? JSON.parse(raw) : {};
      } catch {
        payload = null;
      }

      if (!response.ok) {
        const messageText =
          payload?.error?.message ||
          (raw ? raw.slice(0, 240) : null) ||
          `Batch request failed (${response.status})`;
        throw new Error(messageText);
      }

      sendResponse({
        ok: true,
        results: mergeResults(urls, Array.isArray(payload?.results) ? payload.results : []),
      });
    } catch (error) {
      const messageText =
        error instanceof Error && error.name === "AbortError"
          ? "Batch lookup timed out before the API finished."
          : error instanceof Error
            ? error.message
            : "Unknown extension background error.";
      sendResponse({
        ok: false,
        error: messageText,
      });
    }
  })();

  return true;
});
