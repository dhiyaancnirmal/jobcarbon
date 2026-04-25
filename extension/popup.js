const WEBSITE_BASE = "https://howoldisthisjob.com";
const THEME_KEY = "theme";
const POPUP_STATE_INDEX_KEY = "howoldisthisjob-popup-index-v1";
const POPUP_STATE_KEY_PREFIX = "howoldisthisjob-popup-state:";
const POPUP_STATE_TTL_MS = 12 * 60 * 60 * 1000;
const MAX_STORED_POPUP_STATES = 6;
const POPUP_MESSAGE_TIMEOUT_MS = 125000;

const dom = {
  summary: document.getElementById("scan-summary"),
  scanButton: document.getElementById("scan-button"),
  status: document.getElementById("scan-status"),
  results: document.getElementById("scan-results"),
  loadMoreButton: document.getElementById("load-more-button"),
  themeButtons: Array.from(document.querySelectorAll(".popup__option")),
};

let activeTab = null;
let pageState = null;
let isLoading = false;

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function normalizeText(value) {
  return (value || "").replace(/\s+/g, " ").trim();
}

function compactLabel(value, fallback = "Open job") {
  const normalized = normalizeText(value);
  if (!normalized) return fallback;
  if (normalized.length <= 96) return normalized;
  return `${normalized.slice(0, 93).trimEnd()}...`;
}

function storageKeyForPage(pageUrl) {
  const encoded = btoa(unescape(encodeURIComponent(pageUrl)))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/g, "");
  return `${POPUP_STATE_KEY_PREFIX}${encoded}`;
}

function localGet(area, keys) {
  return new Promise((resolve, reject) => {
    area.get(keys, (value) => {
      const runtimeError = chrome.runtime.lastError;
      if (runtimeError) {
        reject(new Error(runtimeError.message));
        return;
      }
      resolve(value);
    });
  });
}

function localSet(area, value) {
  return new Promise((resolve, reject) => {
    area.set(value, () => {
      const runtimeError = chrome.runtime.lastError;
      if (runtimeError) {
        reject(new Error(runtimeError.message));
        return;
      }
      resolve();
    });
  });
}

function localRemove(area, keys) {
  return new Promise((resolve, reject) => {
    area.remove(keys, () => {
      const runtimeError = chrome.runtime.lastError;
      if (runtimeError) {
        reject(new Error(runtimeError.message));
        return;
      }
      resolve();
    });
  });
}

function queryTabs(queryInfo) {
  return new Promise((resolve, reject) => {
    chrome.tabs.query(queryInfo, (tabs) => {
      const runtimeError = chrome.runtime.lastError;
      if (runtimeError) {
        reject(new Error(runtimeError.message));
        return;
      }
      resolve(tabs);
    });
  });
}

function executeScript(details) {
  return new Promise((resolve, reject) => {
    chrome.scripting.executeScript(details, (results) => {
      const runtimeError = chrome.runtime.lastError;
      if (runtimeError) {
        reject(new Error(runtimeError.message));
        return;
      }
      resolve(results);
    });
  });
}

function sendRuntimeMessage(message, timeoutMs = POPUP_MESSAGE_TIMEOUT_MS) {
  return new Promise((resolve, reject) => {
    let settled = false;
    const timeoutId = window.setTimeout(() => {
      if (settled) return;
      settled = true;
      reject(
        new Error(
          "Extension background timed out while querying job dates. Try again."
        )
      );
    }, timeoutMs);

    const finish = (callback) => {
      if (settled) return;
      settled = true;
      window.clearTimeout(timeoutId);
      callback();
    };

    try {
      chrome.runtime.sendMessage(message, (response) => {
        const runtimeError = chrome.runtime.lastError;
        if (runtimeError) {
          finish(() => reject(new Error(runtimeError.message)));
          return;
        }

        if (typeof response === "undefined") {
          finish(() =>
            reject(
              new Error(
                "Extension background returned no response. Reload the extension and try again."
              )
            )
          );
          return;
        }

        finish(() => resolve(response));
      });
    } catch (error) {
      finish(() =>
        reject(
          error instanceof Error
            ? error
            : new Error("Unknown extension messaging error.")
        )
      );
    }
  });
}

function preferredWindowSize(totalCount) {
  if (totalCount <= 18) return totalCount;

  let fraction = 0.5;
  if (totalCount > 500) {
    fraction = 0.06;
  } else if (totalCount > 250) {
    fraction = 0.1;
  } else if (totalCount > 100) {
    fraction = 0.16;
  } else if (totalCount > 40) {
    fraction = 0.28;
  }

  return clamp(Math.ceil(totalCount * fraction), 12, Math.min(64, totalCount));
}

function preferredBatchSize(totalCount, pendingCount) {
  if (pendingCount <= 0) return 0;

  let batchSize = 8;
  if (totalCount > 500) {
    batchSize = 6;
  } else if (totalCount > 150) {
    batchSize = 7;
  }

  return clamp(batchSize, 4, pendingCount);
}

function preferredConcurrency(totalCount) {
  if (totalCount > 500) return 2;
  if (totalCount > 120) return 3;
  return 4;
}

function pageHost(pageUrl) {
  try {
    return new URL(pageUrl).hostname.replace(/^www\./, "");
  } catch {
    return "this page";
  }
}

function titleForLink(link, item) {
  if (item?.result?.title) return compactLabel(item.result.title, link.label);
  return compactLabel(link.label);
}

function friendlyPlatform(platform) {
  if (!platform) return null;
  return platform
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatDate(isoDate) {
  if (!isoDate) return null;
  const value = new Date(`${isoDate}T00:00:00`);
  if (Number.isNaN(value.getTime())) return null;
  return value.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function ageLabel(isoDate) {
  if (!isoDate) return null;
  const [year, month, day] = isoDate.split("-").map(Number);
  if (!year || !month || !day) return null;

  const today = new Date();
  const localToday = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  const start = new Date(year, month - 1, day);
  const diffDays = Math.floor((localToday.getTime() - start.getTime()) / 86400000);

  if (Number.isNaN(diffDays) || diffDays < 0) return null;
  if (diffDays === 0) return "Today";
  if (diffDays < 30) return `${diffDays}d`;

  const months = Math.floor(diffDays / 30);
  if (months < 12) return `${months}mo`;
  return `${Math.floor(diffDays / 365)}y`;
}

function resultMeta(item) {
  if (!item || (!item.ok && !item.error && !item.result)) {
    return {
      text: "Waiting to scan",
      error: false,
      pending: true,
    };
  }

  if (item?.ok && item.result?.likely_posted_date) {
    const parts = [];
    const age = ageLabel(item.result.likely_posted_date);
    const posted = formatDate(item.result.likely_posted_date);
    const platform = friendlyPlatform(item.result.platform);

    if (age) parts.push(`${age} old`);
    if (posted) parts.push(`Posted ${posted}`);
    if (platform) parts.push(platform);

    return {
      text: parts.join(" · "),
      error: false,
      pending: false,
    };
  }

  if (item?.ok && item.result?.status === "success") {
    return {
      text: "No posting date found",
      error: false,
      pending: false,
    };
  }

  return {
    text: simplifyError(item?.error),
    error: true,
    pending: false,
  };
}

function simplifyError(errorText) {
  const message = normalizeText(errorText);
  if (!message) return "Posting date unavailable right now.";
  if (/timed out/i.test(message)) {
    return "This lookup took too long. Try again.";
  }
  if (/no response|reload the extension/i.test(message)) {
    return "Reload the extension, then try again.";
  }
  if (/network/i.test(message)) {
    return "Network error while checking this posting.";
  }
  return message;
}

function serializeState(state) {
  return {
    pageUrl: state.pageUrl,
    host: state.host,
    totalCount: state.totalCount,
    desiredCount: state.desiredCount,
    orderedLinks: state.orderedLinks,
    itemsByUrl: state.itemsByUrl,
    lastError: state.lastError,
    updatedAt: Date.now(),
  };
}

function hydrateState(raw, fallbackPageUrl) {
  if (!raw || typeof raw !== "object") return null;
  if (typeof raw.pageUrl !== "string" || raw.pageUrl !== fallbackPageUrl) return null;

  const orderedLinks = Array.isArray(raw.orderedLinks)
    ? raw.orderedLinks
        .filter((item) => item && typeof item.url === "string")
        .map((item) => ({
          url: item.url,
          label: compactLabel(item.label),
        }))
    : [];

  const itemsByUrl = {};
  if (raw.itemsByUrl && typeof raw.itemsByUrl === "object") {
    for (const [url, item] of Object.entries(raw.itemsByUrl)) {
      if (!item || typeof url !== "string") continue;
      itemsByUrl[url] = item;
    }
  }

  return {
    pageUrl: raw.pageUrl,
    host: typeof raw.host === "string" ? raw.host : pageHost(raw.pageUrl),
    totalCount: Number.isFinite(raw.totalCount) ? raw.totalCount : orderedLinks.length,
    desiredCount: Number.isFinite(raw.desiredCount) ? raw.desiredCount : 0,
    orderedLinks,
    itemsByUrl,
    lastError: typeof raw.lastError === "string" ? raw.lastError : "",
  };
}

async function loadPersistedState(pageUrl) {
  const key = storageKeyForPage(pageUrl);
  const payload = await localGet(chrome.storage.local, [key]);
  const rawState = payload[key];
  const state = hydrateState(rawState, pageUrl);
  if (!state) return null;
  if ((rawState.updatedAt || 0) < Date.now() - POPUP_STATE_TTL_MS) {
    await localRemove(chrome.storage.local, [key]);
    return null;
  }
  return state;
}

async function savePersistedState(state) {
  const key = storageKeyForPage(state.pageUrl);
  const indexPayload = await localGet(chrome.storage.local, [POPUP_STATE_INDEX_KEY]);
  const index = indexPayload[POPUP_STATE_INDEX_KEY] || {};
  index[key] = Date.now();

  const staleKeys = Object.entries(index)
    .filter(([, timestamp]) => (timestamp || 0) < Date.now() - POPUP_STATE_TTL_MS)
    .map(([entryKey]) => entryKey);

  for (const staleKey of staleKeys) {
    delete index[staleKey];
  }

  const sortedKeys = Object.entries(index).sort((left, right) => right[1] - left[1]);
  const removeKeys = sortedKeys
    .slice(MAX_STORED_POPUP_STATES)
    .map(([entryKey]) => entryKey);

  for (const removeKey of removeKeys) {
    delete index[removeKey];
  }

  const writePayload = {
    [key]: serializeState(state),
    [POPUP_STATE_INDEX_KEY]: index,
  };

  await localSet(chrome.storage.local, writePayload);
  if (staleKeys.length || removeKeys.length) {
    await localRemove(chrome.storage.local, [...staleKeys, ...removeKeys]);
  }
}

function mergeLinksIntoState(existingState, tabUrl, links) {
  const byUrl = existingState?.itemsByUrl || {};
  const orderedLinks = links.map((link) => ({
    url: link.url,
    label: compactLabel(link.label),
  }));

  const nextItemsByUrl = {};
  for (const link of orderedLinks) {
    const existingItem = byUrl[link.url];
    if (existingItem) {
      nextItemsByUrl[link.url] = {
        ...existingItem,
        label: compactLabel(existingItem.label || link.label),
      };
      continue;
    }
    nextItemsByUrl[link.url] = {
      url: link.url,
      label: link.label,
    };
  }

  return {
    pageUrl: tabUrl,
    host: pageHost(tabUrl),
    totalCount: orderedLinks.length,
    desiredCount: Math.min(existingState?.desiredCount || 0, orderedLinks.length),
    orderedLinks,
    itemsByUrl: nextItemsByUrl,
    lastError: existingState?.lastError || "",
  };
}

function attemptedCount(state) {
  return state.orderedLinks
    .slice(0, state.desiredCount)
    .filter((link) => {
      const item = state.itemsByUrl[link.url];
      return Boolean(item?.ok) || Boolean(item?.error);
    }).length;
}

function datedCount(state) {
  return state.orderedLinks
    .slice(0, state.desiredCount)
    .filter((link) => state.itemsByUrl[link.url]?.result?.likely_posted_date).length;
}

function pendingLinksForDesiredWindow(state) {
  return state.orderedLinks
    .slice(0, state.desiredCount)
    .filter((link) => {
      const item = state.itemsByUrl[link.url];
      return !item?.ok && !item?.result?.likely_posted_date;
    });
}

function unattemptedLinksForDesiredWindow(state) {
  return state.orderedLinks
    .slice(0, state.desiredCount)
    .filter((link) => {
      const item = state.itemsByUrl[link.url];
      return !item?.ok && !item?.error && !item?.result;
    });
}

function resultSortRank(item) {
  if (item?.result?.likely_posted_date) return 0;
  if (!item || (!item.ok && !item.error && !item.result)) return 1;
  if (item?.ok) return 2;
  return 3;
}

function updateStatus(text, tone = "") {
  dom.status.textContent = text || "";
  if (tone) {
    dom.status.dataset.tone = tone;
  } else {
    delete dom.status.dataset.tone;
  }
}

function renderSummary() {
  if (!pageState || !activeTab?.url) {
    dom.summary.textContent = "Ready to scan this site for supported job links.";
    return;
  }

  if (pageState.totalCount === 0) {
    dom.summary.textContent = `No supported ATS job links found on ${pageState.host}.`;
    return;
  }

  const attempted = attemptedCount(pageState);
  const dated = datedCount(pageState);
  const windowSize = preferredWindowSize(pageState.totalCount);

  if (pageState.desiredCount === 0) {
    dom.summary.textContent = `Found ${pageState.totalCount} supported job links on ${pageState.host}. Ready to load ${windowSize} now.`;
    return;
  }

  dom.summary.textContent = `Loaded ${attempted} of ${pageState.totalCount} links. ${dated} already have posting dates.`;
}

function renderResults() {
  const visibleLinks = (pageState?.orderedLinks?.slice(0, pageState.desiredCount) || [])
    .map((link, index) => ({ link, index }))
    .sort((left, right) => {
      const leftRank = resultSortRank(pageState.itemsByUrl[left.link.url]);
      const rightRank = resultSortRank(pageState.itemsByUrl[right.link.url]);
      return leftRank - rightRank || left.index - right.index;
    })
    .map((entry) => entry.link);
  dom.results.textContent = "";
  dom.results.hidden = visibleLinks.length === 0;

  if (visibleLinks.length === 0) {
    return;
  }

  for (const link of visibleLinks) {
    const item = pageState.itemsByUrl[link.url];
    const resultLink = document.createElement("a");
    resultLink.className = "popup__result";
    resultLink.href = `${WEBSITE_BASE}/?url=${encodeURIComponent(link.url)}`;
    resultLink.target = "_blank";
    resultLink.rel = "noreferrer";

    const title = document.createElement("div");
    title.className = "popup__result-title";
    title.textContent = titleForLink(link, item);

    const meta = document.createElement("div");
    const metaInfo = resultMeta(item);
    meta.className = metaInfo.error
      ? "popup__result-meta popup__result-meta--error"
      : "popup__result-meta";
    meta.textContent = metaInfo.text;

    resultLink.append(title, meta);
    dom.results.append(resultLink);
  }
}

function renderButtons() {
  const hasResults = pageState && pageState.totalCount > 0;
  const canLoadMore =
    hasResults && pageState.desiredCount < pageState.totalCount && !isLoading;
  const increment = hasResults ? preferredWindowSize(pageState.totalCount) : 0;
  const remaining = hasResults ? pageState.totalCount - pageState.desiredCount : 0;
  const loadMoreAmount = Math.min(increment, remaining);

  dom.scanButton.disabled = !hasResults || isLoading;
  dom.scanButton.textContent = isLoading
    ? "Scanning..."
    : pageState?.desiredCount
      ? "Continue scan"
      : "Scan current page";

  dom.loadMoreButton.hidden = !canLoadMore;
  dom.loadMoreButton.disabled = !canLoadMore;
  dom.loadMoreButton.textContent = loadMoreAmount
    ? `Load ${loadMoreAmount} more`
    : "Load more";
}

function renderState() {
  renderSummary();
  renderResults();
  renderButtons();
}

async function getActiveTab() {
  const tabs = await queryTabs({ active: true, currentWindow: true });
  return tabs[0] || null;
}

async function scanPageForSupportedLinks(tabId) {
  const [injection] = await executeScript({
    target: { tabId },
    func: () => {
      const URL_LIKE_ATTRIBUTE = /(url|href|target|apply|redirect|destination)/i;
      const WRAPPED_URL_PARAM_KEYS = [
        "url",
        "dest",
        "destination",
        "redirect",
        "redir",
        "target",
        "u",
        "q",
        "applyUrl",
        "applyurl",
        "trkUrl",
        "trkurl",
      ];

      function normalizeText(value) {
        return (value || "").replace(/\s+/g, " ").trim();
      }

      function canonicalizeUrl(url) {
        try {
          const parsed = new URL(url, window.location.href);
          if (parsed.hostname.toLowerCase().endsWith(".icims.com")) {
            for (const key of [
              "mobile",
              "width",
              "height",
              "bga",
              "needsRedirect",
              "jan1offset",
              "jun1offset",
            ]) {
              parsed.searchParams.delete(key);
            }
          }
          const keepHash =
            parsed.hostname.toLowerCase().includes("brassring.com") &&
            /jobDetails=\d+/i.test(parsed.hash);
          parsed.hash = keepHash ? parsed.hash : "";
          parsed.pathname = parsed.pathname.replace(/\/+$/, "") || "/";
          return `${parsed.origin}${parsed.pathname}${parsed.search}`;
        } catch {
          return null;
        }
      }

      function isSupportedDetailUrl(url) {
        try {
          const parsed = new URL(url, window.location.href);
          const host = parsed.hostname.toLowerCase();
          const segments = parsed.pathname.split("/").filter(Boolean);

          if (host === "jobs.lever.co") return segments.length === 2;
          if (host === "boards.greenhouse.io" || host === "job-boards.greenhouse.io") {
            return segments.includes("jobs");
          }
          if (host === "jobs.ashbyhq.com") {
            const jobId = segments[1] || "";
            return (
              segments.length >= 2 &&
              /^[0-9a-f]{8}-[0-9a-f-]{27,}$/i.test(jobId) &&
              (segments.length === 2 || segments[2] === "application")
            );
          }
          if (host === "jobs.smartrecruiters.com") return segments.length >= 2;
          if (host === "apply.workable.com") {
            return segments.length >= 3 && segments[1] === "j";
          }
          if (host === "jobs.workable.com") {
            return segments.length >= 2 && segments[0] === "view";
          }
          if (host === "jobs.dayforcehcm.com") return segments.includes("jobs");
          if (host.endsWith(".pageuppeople.com")) return segments.includes("job");
          if (host.endsWith(".teamtailor.com")) {
            return segments.includes("jobs") || /^\d+(?:-[a-z0-9-]+)?$/i.test(segments.at(-1) || "");
          }
          if (host.endsWith(".recruitee.com")) {
            return segments[0] === "o" && segments.length >= 2;
          }
          if (host.endsWith(".jobs.personio.de")) {
            return segments[0] === "job" && segments.length >= 2;
          }
          if ((host === "jobs.breezy.hr" || host.endsWith(".breezy.hr")) && segments[0] === "p") {
            return segments.length >= 2;
          }
          if (host.endsWith(".applytojob.com") && segments[0] === "apply") {
            if (segments[1] === "jobs" && segments[2] === "details") return segments.length >= 4;
            return segments.length >= 2;
          }
          if (host === "app.dover.com") return segments.length >= 3 && segments[0] === "apply";
          if (host === "ats.rippling.com") return segments.length >= 3;
          if (host.endsWith(".myworkdayjobs.com")) return segments.includes("job");
          if (host.endsWith(".bamboohr.com")) return segments.includes("careers") && segments.length >= 2;
          if (host.includes("brassring.com")) {
            return parsed.searchParams.has("jobid") || parsed.searchParams.has("JobId") || /jobDetails=\d+/i.test(parsed.hash);
          }
          if (host === "jobs.sap.com") return segments[0] === "job" && segments.length >= 3;
          if (host.includes("successfactors") || parsed.pathname.toLowerCase().includes("successfactors")) {
            return segments[0] === "job" ? segments.length >= 3 : segments.length > 0;
          }
          if (host === "workforcenow.adp.com") return parsed.searchParams.has("jobId");
          if (host === "careers.paycor.com") return parsed.searchParams.get("gnk") === "job";
          if (host === "jobs.gem.com") return segments.length === 2;
          if (host.includes("taleo.net")) return parsed.searchParams.has("rid") || parsed.searchParams.has("job");
          if (host.endsWith(".ultipro.com")) {
            return segments.includes("JobBoard") && parsed.searchParams.has("opportunityId");
          }
          if (host.endsWith(".icims.com")) return segments.includes("jobs");
          if (host.endsWith(".avature.net")) return segments.includes("JobDetail");
          if (host.endsWith(".oraclecloud.com") && parsed.pathname.includes("/hcmUI/")) {
            return segments.includes("job") || segments.includes("requisitions");
          }
          if (host.includes("jobvite.com")) {
            return parsed.searchParams.has("j") || (segments[1] === "job" && segments.length >= 3);
          }
          if (parsed.searchParams.get("gnk") === "job") return true;
          return false;
        } catch {
          return false;
        }
      }

      function resolveSupportedDetailUrl(url, seen = new Set()) {
        const normalized = canonicalizeUrl(url);
        if (!normalized || seen.has(normalized)) return null;
        seen.add(normalized);
        if (isSupportedDetailUrl(normalized)) return normalized;

        try {
          const parsed = new URL(normalized);
          for (const key of WRAPPED_URL_PARAM_KEYS) {
            const candidate = parsed.searchParams.get(key);
            if (!candidate) continue;
            const resolved = resolveSupportedDetailUrl(candidate, seen);
            if (resolved) return resolved;
          }
        } catch {
          return null;
        }

        return null;
      }

      function isVisible(anchor) {
        return (
          anchor instanceof HTMLElement &&
          !!anchor.href &&
          anchor.getClientRects().length > 0 &&
          anchor.dataset.howoldisthisjobIgnore !== "true"
        );
      }

      function collectAnchorCandidates(anchor) {
        const candidates = [anchor.href];
        for (const name of anchor.getAttributeNames()) {
          if (!URL_LIKE_ATTRIBUTE.test(name)) continue;
          const value = anchor.getAttribute(name);
          if (value) candidates.push(value);
        }
        return candidates;
      }

      function findTitleElement(root) {
        if (!(root instanceof Element)) return null;
        const selector = [
          "h1",
          "h2",
          "h3",
          "h4",
          "h5",
          "[role='heading']",
          ".ashby-job-posting-brief-title",
          "p[class*='body--medium']",
          "[class*='jobPostingHeader']",
          "[class*='job-title']",
          "[class*='jobTitle']",
          "[class*='posting-title']",
          "[data-ui='job-title']",
          "[data-testid*='title']",
          "[itemprop='title']",
        ].join(", ");
        if (root.matches(selector)) return root;
        return root.querySelector(selector);
      }

      function looksLikeJobLink(anchor, resolvedUrl) {
        if (!(anchor instanceof HTMLElement)) return false;

        const normalizedText = normalizeText(anchor.textContent);
        if (!normalizedText || /^(apply(?: now)?|learn more|details?)$/i.test(normalizedText)) {
          return false;
        }

        const combinedClassText = [
          anchor.className,
          anchor.parentElement?.className,
          anchor.firstElementChild?.className,
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();

        let resolvedHost = window.location.hostname;
        try {
          resolvedHost = new URL(resolvedUrl).hostname.toLowerCase();
        } catch {}

        if (resolvedHost === "jobs.gem.com") {
          return (
            combinedClassText.includes("jobpostinglink") ||
            !!anchor.closest('[class*="jobPosting"]')
          );
        }

        if (findTitleElement(anchor)) return true;
        if (/(job|posting|opening|position|role|opportunity)/.test(combinedClassText)) {
          return true;
        }

        return normalizedText.length >= 24 && /\s/.test(normalizedText);
      }

      function labelForAnchor(anchor) {
        const ownText = normalizeText(anchor.textContent);
        if (ownText && !/^(apply(?: now)?|learn more|details?)$/i.test(ownText)) {
          return ownText;
        }

        const container = anchor.closest(
          "li, article, tr, [role='listitem'], [class*='job'], [class*='opening'], [class*='posting'], [class*='position'], [data-testid*='job']"
        );
        if (container instanceof HTMLElement) {
          const title = container.querySelector(
            "h1, h2, h3, h4, h5, [role='heading'], [data-ui='job-title'], [class*='job-title'], [class*='jobTitle'], [class*='posting-title'], [itemprop='title']"
          );
          const titleText = normalizeText(title?.textContent);
          if (titleText) return titleText;
        }

        return ownText || "Open job";
      }

      const results = [];
      const seen = new Set();

      const currentPageUrl = resolveSupportedDetailUrl(window.location.href);
      if (currentPageUrl) {
        const title = normalizeText(
          document.querySelector("h1, [role='heading'], [itemprop='title']")?.textContent
        );
        seen.add(currentPageUrl);
        results.push({
          url: currentPageUrl,
          label: title || document.title || "Current job",
        });
      }

      for (const anchor of document.querySelectorAll("a[href]")) {
        if (!isVisible(anchor)) continue;

        let resolvedUrl = null;
        for (const candidate of collectAnchorCandidates(anchor)) {
          resolvedUrl = resolveSupportedDetailUrl(candidate);
          if (resolvedUrl) break;
        }

        if (!resolvedUrl || seen.has(resolvedUrl)) continue;
        if (!looksLikeJobLink(anchor, resolvedUrl)) continue;
        seen.add(resolvedUrl);
        results.push({
          url: resolvedUrl,
          label: labelForAnchor(anchor),
        });
      }

      return results;
    },
  });

  return Array.isArray(injection?.result) ? injection.result : [];
}

async function refreshLinks({ preserveStatus = true } = {}) {
  if (!activeTab?.id || !activeTab.url) {
    return;
  }

  const links = await scanPageForSupportedLinks(activeTab.id);
  pageState = mergeLinksIntoState(preserveStatus ? pageState : null, activeTab.url, links);
  await savePersistedState(pageState);
  renderState();
}

async function runBatches(links) {
  if (!links.length) return;

  const batchSize = preferredBatchSize(pageState.totalCount, links.length);
  const concurrency = preferredConcurrency(pageState.totalCount);
  let cursor = 0;
  let firstError = "";

  async function worker() {
    while (cursor < links.length) {
      const start = cursor;
      cursor += batchSize;
      const batch = links.slice(start, start + batchSize);
      if (!batch.length) return;

      updateStatus(
        `Querying ${batch.length} posting date${batch.length === 1 ? "" : "s"}...`
      );

      try {
        const response = await sendRuntimeMessage({
          type: "howoldisthisjob:batch-estimate",
          urls: batch.map((link) => link.url),
        });

        if (!response?.ok || !Array.isArray(response.results)) {
          throw new Error(
            response?.error || "Extension batch lookup failed because the background response was invalid."
          );
        }

        for (const resultItem of response.results) {
          const currentItem = pageState.itemsByUrl[resultItem.url] || { url: resultItem.url };
          pageState.itemsByUrl[resultItem.url] = {
            ...currentItem,
            ok: Boolean(resultItem.ok),
            result: resultItem.ok ? resultItem.result : null,
            error: resultItem.ok ? "" : resultItem.error?.message || "Unknown extension error.",
          };
        }
      } catch (error) {
        const message =
          error instanceof Error
            ? error.message
            : "Unknown extension error while querying job dates.";
        if (!firstError) firstError = message;
        for (const link of batch) {
          const currentItem = pageState.itemsByUrl[link.url] || { url: link.url, label: link.label };
          pageState.itemsByUrl[link.url] = {
            ...currentItem,
            ok: false,
            result: null,
            error: message,
          };
        }
      }

      await savePersistedState(pageState);
      renderState();
    }
  }

  const workers = Array.from({ length: Math.min(concurrency, Math.ceil(links.length / batchSize)) }, () =>
    worker()
  );
  await Promise.all(workers);

  if (firstError) {
    pageState.lastError = firstError;
    updateStatus(simplifyError(firstError), "error");
  } else {
    pageState.lastError = "";
    updateStatus("");
  }
  await savePersistedState(pageState);
  renderState();
}

async function resumeScan() {
  if (!pageState || isLoading) return;
  if (pageState.totalCount === 0) {
    renderState();
    return;
  }

  if (pageState.desiredCount === 0) {
    pageState.desiredCount = preferredWindowSize(pageState.totalCount);
  }

  const pendingLinks = pendingLinksForDesiredWindow(pageState);
  if (!pendingLinks.length) {
    updateStatus("Everything in the current window is already loaded.");
    renderState();
    return;
  }

  isLoading = true;
  renderButtons();
  await savePersistedState(pageState);

  try {
    await runBatches(pendingLinks);
  } finally {
    isLoading = false;
    renderButtons();
  }
}

async function handleScanClick() {
  try {
    updateStatus("");
    await refreshLinks({ preserveStatus: true });
    await resumeScan();
  } catch (error) {
    updateStatus(simplifyError(error instanceof Error ? error.message : ""), "error");
  }
}

async function handleLoadMore() {
  if (!pageState || isLoading) return;

  pageState.desiredCount = Math.min(
    pageState.totalCount,
    pageState.desiredCount + preferredWindowSize(pageState.totalCount)
  );
  await savePersistedState(pageState);
  renderState();
  await resumeScan();
}

async function applyTheme(theme) {
  const nextTheme = theme === "dark" ? "dark" : "light";
  await localSet(chrome.storage.sync, { [THEME_KEY]: nextTheme });
  for (const button of dom.themeButtons) {
    button.setAttribute(
      "aria-checked",
      button.dataset.theme === nextTheme ? "true" : "false"
    );
  }
}

async function initTheme() {
  const prefs = await localGet(chrome.storage.sync, { [THEME_KEY]: "light" });
  const currentTheme = prefs[THEME_KEY] === "dark" ? "dark" : "light";
  for (const button of dom.themeButtons) {
    button.setAttribute(
      "aria-checked",
      button.dataset.theme === currentTheme ? "true" : "false"
    );
    button.addEventListener("click", () => {
      void applyTheme(button.dataset.theme);
    });
  }
}

async function init() {
  await initTheme();

  dom.scanButton.addEventListener("click", () => {
    void handleScanClick();
  });
  dom.loadMoreButton.addEventListener("click", () => {
    void handleLoadMore();
  });

  activeTab = await getActiveTab();
  if (!activeTab?.id || !activeTab.url || !/^https?:/i.test(activeTab.url)) {
    dom.summary.textContent = "Open a normal website tab to scan it for supported ATS job links.";
    dom.scanButton.disabled = true;
    dom.loadMoreButton.hidden = true;
    return;
  }

  pageState = await loadPersistedState(activeTab.url);
  if (pageState) {
    renderState();
    if (pageState.lastError) {
      updateStatus(simplifyError(pageState.lastError), "error");
    }
  }

  try {
    await refreshLinks({ preserveStatus: true });
    if (
      pageState?.desiredCount > 0 &&
      unattemptedLinksForDesiredWindow(pageState).length > 0
    ) {
      await resumeScan();
    }
  } catch (error) {
    updateStatus(
      simplifyError(error instanceof Error ? error.message : "Unable to scan this page."),
      "error"
    );
  }
}

void init();
