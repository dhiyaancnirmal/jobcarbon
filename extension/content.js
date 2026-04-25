const RESULT_CACHE = new Map();
const PENDING_URLS = new Set();
const WEBSITE_BASE = "https://howoldisthisjob.com";
const BADGE_LOGO_URL = chrome.runtime.getURL("logo-badge.svg");
const CONTENT_MESSAGE_TIMEOUT_MS = 125000;
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
const LIST_TITLE_SELECTORS = [
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
];

let scanTimer = null;
let scanInFlight = false;
let rescanRequested = false;
const LIST_FETCH_BATCH_SIZE = 8;
const LIST_FETCH_VIEWPORT_MARGIN_PX = 900;

function sendRuntimeMessage(message, timeoutMs = CONTENT_MESSAGE_TIMEOUT_MS) {
  return new Promise((resolve, reject) => {
    let settled = false;
    const timeoutId = window.setTimeout(() => {
      if (settled) return;
      settled = true;
      reject(
        new Error(
          "Extension background timed out. Reload the extension in chrome://extensions and try again."
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
                "Extension background returned no response. Reload the extension in chrome://extensions and try again."
              )
            )
          );
          return;
        }

        finish(() => resolve(response));
      });
    } catch (error) {
      finish(() =>
        reject(error instanceof Error ? error : new Error("Unknown extension messaging error."))
      );
    }
  });
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

    if (host === "jobs.lever.co") {
      return segments.length === 2;
    }
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
    if (host === "jobs.smartrecruiters.com") {
      return segments.length >= 2;
    }
    if (host === "apply.workable.com") {
      return segments.length >= 3 && segments[1] === "j";
    }
    if (host === "jobs.workable.com") {
      return segments.length >= 2 && segments[0] === "view";
    }
    if (host === "jobs.dayforcehcm.com") {
      return segments.includes("jobs");
    }
    if (host.endsWith(".pageuppeople.com")) {
      return segments.includes("job");
    }
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
      if (segments[1] === "jobs" && segments[2] === "details") {
        return segments.length >= 4;
      }
      return segments.length >= 2;
    }
    if (host === "app.dover.com") {
      return segments.length >= 3 && segments[0] === "apply";
    }
    if (host === "ats.rippling.com") {
      return segments.length >= 3;
    }
    if (host.endsWith(".myworkdayjobs.com")) {
      return segments.includes("job");
    }
    if (host.endsWith(".bamboohr.com")) {
      return segments.includes("careers") && segments.length >= 2;
    }
    if (host.includes("brassring.com")) {
      return (
        parsed.searchParams.has("jobid") ||
        parsed.searchParams.has("JobId") ||
        /jobDetails=\d+/i.test(parsed.hash)
      );
    }
    if (host === "jobs.sap.com") {
      return segments[0] === "job" && segments.length >= 3;
    }
    if (host.includes("successfactors") || parsed.pathname.toLowerCase().includes("successfactors")) {
      return segments[0] === "job" ? segments.length >= 3 : segments.length > 0;
    }
    if (host === "workforcenow.adp.com") {
      return parsed.searchParams.has("jobId");
    }
    if (host === "careers.paycor.com") {
      return parsed.searchParams.get("gnk") === "job";
    }
    if (host === "jobs.gem.com") {
      return segments.length === 2;
    }
    if (host.includes("taleo.net")) {
      return parsed.searchParams.has("rid") || parsed.searchParams.has("job");
    }
    if (host.endsWith(".ultipro.com")) {
      return segments.includes("JobBoard") && parsed.searchParams.has("opportunityId");
    }
    if (host.endsWith(".icims.com")) {
      return segments.includes("jobs");
    }
    if (host.endsWith(".avature.net")) {
      return segments.includes("JobDetail");
    }
    if (host.endsWith(".oraclecloud.com") && parsed.pathname.includes("/hcmUI/")) {
      return segments.includes("job") || segments.includes("requisitions");
    }
    if (host.includes("jobvite.com")) {
      return parsed.searchParams.has("j") || (segments[1] === "job" && segments.length >= 3);
    }
    if (parsed.searchParams.get("gnk") === "job") {
      return true;
    }

    return false;
  } catch {
    return false;
  }
}

function resolveSupportedDetailUrl(url, seen = new Set()) {
  const normalized = canonicalizeUrl(url);
  if (!normalized || seen.has(normalized)) {
    return null;
  }

  seen.add(normalized);
  if (isSupportedDetailUrl(normalized)) {
    return normalized;
  }

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
  if (!(anchor instanceof HTMLElement)) return false;
  if (anchor.dataset.howoldisthisjobIgnore === "true") return false;
  if (!anchor.href || !anchor.textContent?.trim()) return false;
  return anchor.getClientRects().length > 0;
}

function looksLikeJobLink(anchor, resolvedUrl) {
  if (!(anchor instanceof HTMLElement)) return false;

  const combinedClassText = [
    anchor.className,
    anchor.parentElement?.className,
    anchor.firstElementChild?.className,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  const normalizedText = anchor.textContent?.replace(/\s+/g, " ").trim() || "";
  if (/^(apply|learn more|details?)$/i.test(normalizedText)) {
    return false;
  }
  let resolvedHost = window.location.hostname;
  try {
    if (resolvedUrl) {
      resolvedHost = new URL(resolvedUrl).hostname.toLowerCase();
    }
  } catch {}

  if (resolvedHost === "jobs.gem.com") {
    return (
      combinedClassText.includes("jobpostinglink") ||
      !!anchor.closest('[class*="jobPosting"]')
    );
  }

  if (findTitleElement(anchor)) {
    return true;
  }
  if (/(job|posting|opening|position|role|opportunity)/.test(combinedClassText)) {
    return true;
  }

  return normalizedText.length >= 24 && /\s/.test(normalizedText);
}

function collectAnchorCandidates(anchor) {
  const candidates = [anchor.href];

  for (const name of anchor.getAttributeNames()) {
    if (!URL_LIKE_ATTRIBUTE.test(name)) continue;
    const value = anchor.getAttribute(name);
    if (value) {
      candidates.push(value);
    }
  }

  return candidates;
}

function addAnchorToMap(map, resolvedUrl, anchor) {
  const list = map.get(resolvedUrl);
  if (list) {
    if (!list.includes(anchor)) {
      list.push(anchor);
    }
  } else {
    map.set(resolvedUrl, [anchor]);
  }
}

function collectAnchorsByUrl() {
  const anchorsByUrl = new Map();

  for (const anchor of document.querySelectorAll("a[href]")) {
    if (!isVisible(anchor)) continue;

    let normalized = null;
    for (const candidate of collectAnchorCandidates(anchor)) {
      normalized = resolveSupportedDetailUrl(candidate);
      if (normalized) break;
    }
    if (!normalized) continue;
    if (!looksLikeJobLink(anchor, normalized)) continue;

    addAnchorToMap(anchorsByUrl, normalized, anchor);
  }

  return anchorsByUrl;
}

function prioritizeListUrls(anchorsByUrl) {
  const viewportHeight = window.innerHeight || 0;
  return Array.from(anchorsByUrl.entries())
    .map(([url, anchors]) => {
      const firstAnchor = anchors[0];
      const rect = firstAnchor.getBoundingClientRect();
      const inViewport = rect.bottom > 0 && rect.top < viewportHeight + 160;
      const nearViewport =
        rect.bottom > -LIST_FETCH_VIEWPORT_MARGIN_PX &&
        rect.top < viewportHeight + LIST_FETCH_VIEWPORT_MARGIN_PX;
      return { url, top: rect.top, inViewport, nearViewport };
    })
    .sort((left, right) => {
      if (left.inViewport !== right.inViewport) {
        return left.inViewport ? -1 : 1;
      }
      if (left.nearViewport !== right.nearViewport) {
        return left.nearViewport ? -1 : 1;
      }
      return left.top - right.top;
    })
    .map((entry) => entry.url);
}

function hasNearViewportAnchor(anchors) {
  const viewportHeight = window.innerHeight || 0;
  return anchors.some((anchor) => {
    const rect = anchor.getBoundingClientRect();
    return (
      rect.bottom > -LIST_FETCH_VIEWPORT_MARGIN_PX &&
      rect.top < viewportHeight + LIST_FETCH_VIEWPORT_MARGIN_PX
    );
  });
}

function getRefreshDate(result) {
  const dates = Array.isArray(result?.all_dates) ? result.all_dates : [];
  const latest = dates
    .filter((item) => item?.kind === "refresh")
    .map((item) => item.date)
    .filter(Boolean)
    .sort()
    .at(-1);

  return latest && latest !== result?.likely_posted_date ? latest : null;
}

function ageLabel(isoDate) {
  if (!isoDate) return null;
  const [year, month, day] = isoDate.split("-").map(Number);
  if (!year || !month || !day) return null;

  const today = new Date();
  const start = new Date(year, month - 1, day);
  const localToday = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  const diffDays = Math.floor((localToday.getTime() - start.getTime()) / 86400000);

  if (Number.isNaN(diffDays) || diffDays < 0) return null;
  if (diffDays === 0) return "Today";
  if (diffDays < 30) return `${diffDays}d`;

  const months = Math.floor(diffDays / 30);
  if (months < 12) return `${months}mo`;

  return `${Math.floor(diffDays / 365)}y`;
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

function normalizeText(value) {
  return (value || "").replace(/\s+/g, " ").trim();
}

function badgeTitle(result) {
  const posted = formatDate(result?.likely_posted_date);
  const refreshed = formatDate(getRefreshDate(result));
  const title = result?.title || "Job";
  const parts = [`${title}: ${posted ? `originally posted ${posted}` : "posted date unknown"}`];

  if (refreshed) {
    parts.push(`last refreshed ${refreshed}`);
  }
  if (result?.confidence) {
    parts.push(`${result.confidence} confidence`);
  }

  return parts.join(" · ");
}

function buildResultHref(resolvedUrl) {
  return `${WEBSITE_BASE}/?url=${encodeURIComponent(resolvedUrl)}`;
}

function findTitleElement(root) {
  if (!(root instanceof Element)) return null;
  if (root.matches(LIST_TITLE_SELECTORS.join(", "))) {
    return root;
  }
  return root.querySelector(LIST_TITLE_SELECTORS.join(", "));
}

function isElementVisible(element) {
  return (
    element instanceof HTMLElement &&
    element.getClientRects().length > 0 &&
    getComputedStyle(element).visibility !== "hidden"
  );
}

function isBadDetailTitleCandidate(element) {
  return (
    !(element instanceof HTMLElement) ||
    !!element.closest(
      [
        "nav",
        "[role='navigation']",
        "[role='tablist']",
        "[role='tab']",
        "[aria-controls]",
        "[data-testid*='tab']",
      ].join(", ")
    )
  );
}

function getListBadgeHost(anchor) {
  return (
    findTitleElement(anchor) ||
    findTitleElement(anchor.firstElementChild) ||
    findTitleElement(anchor.parentElement) ||
    anchor
  );
}

function ensureBadge(host, result, resolvedUrl, context) {
  if (!(host instanceof HTMLElement)) return;

  const text = ageLabel(result?.likely_posted_date);
  const selector = `.howoldisthisjob-age-badge[data-howoldisthisjob-context="${context}"][data-howoldisthisjob-url="${CSS.escape(
    resolvedUrl
  )}"]`;
  const hostIsLink = host.tagName === "A";
  const existing = hostIsLink
    ? host.nextElementSibling instanceof HTMLElement && host.nextElementSibling.matches(selector)
      ? host.nextElementSibling
      : null
    : host.querySelector(selector);

  if (!text) {
    existing?.remove();
    return;
  }

  let badge = existing;
  if (!(badge instanceof HTMLElement)) {
    badge = document.createElement("a");
    badge.className = "howoldisthisjob-age-badge";
    badge.dataset.howoldisthisjobContext = context;
    badge.dataset.howoldisthisjobUrl = resolvedUrl;
    badge.target = "_blank";
    badge.rel = "noopener noreferrer";
    if (context === "detail") {
      badge.classList.add("howoldisthisjob-age-badge--detail");
    }
    if (hostIsLink) {
      host.insertAdjacentElement("afterend", badge);
    } else {
      host.appendChild(badge);
    }
  }

  if (
    !badge.querySelector(".howoldisthisjob-age-badge__logo") ||
    !badge.querySelector(".howoldisthisjob-age-badge__label")
  ) {
    badge.innerHTML = `
      <img class="howoldisthisjob-age-badge__logo" src="${BADGE_LOGO_URL}" alt="" />
      <span class="howoldisthisjob-age-badge__label"></span>
    `;
  }

  badge.href = buildResultHref(resolvedUrl);
  badge.dataset.confidence = result?.confidence || "unknown";
  badge.setAttribute(
    "aria-label",
    `Open How Old Is This Job? for ${result?.title || "this job"}`
  );
  badge.title = `${badgeTitle(result)} · Open in How Old Is This Job?`;
  const label = badge.querySelector(".howoldisthisjob-age-badge__label");
  if (label instanceof HTMLElement) {
    label.textContent = text;
  }
  applyThemeAttribute(badge);
}

let CURRENT_THEME = "light";

function applyThemeAttribute(element) {
  if (CURRENT_THEME === "dark") {
    element.dataset.theme = "dark";
  } else {
    delete element.dataset.theme;
  }
}

function applyThemeToAll() {
  document
    .querySelectorAll(".howoldisthisjob-age-badge, .howoldisthisjob-detail-card")
    .forEach((node) => {
      if (node instanceof HTMLElement) applyThemeAttribute(node);
    });
}

chrome.storage?.sync.get({ theme: "light" }, (prefs) => {
  CURRENT_THEME = prefs.theme === "dark" ? "dark" : "light";
  applyThemeToAll();
});

chrome.storage?.onChanged.addListener((changes, area) => {
  if (area === "sync" && changes.theme) {
    CURRENT_THEME = changes.theme.newValue === "dark" ? "dark" : "light";
    applyThemeToAll();
  }
});

function clearListBadge(anchor) {
  const host = getListBadgeHost(anchor);
  if (!(host instanceof HTMLElement)) return;

  if (host.tagName === "A") {
    const next = host.nextElementSibling;
    if (
      next instanceof HTMLElement &&
      next.matches('.howoldisthisjob-age-badge[data-howoldisthisjob-context="list"]')
    ) {
      next.remove();
    }
    return;
  }

  for (const badge of host.querySelectorAll('.howoldisthisjob-age-badge[data-howoldisthisjob-context="list"]')) {
    badge.remove();
  }
}

function getDetailRoot() {
  return (
    document.querySelector("main") ||
    document.querySelector("article") ||
    document.querySelector("[role='main']") ||
    document.body
  );
}

function scoreDetailTitleHost(element, resultTitle) {
  const text = normalizeText(element.textContent);
  const normalizedResultTitle = normalizeText(resultTitle);
  const top = element.getBoundingClientRect().top;
  const classText = String(element.className || "").toLowerCase();

  let score = 0;
  if (text && normalizedResultTitle) {
    if (text === normalizedResultTitle) score += 10;
    else if (text.startsWith(normalizedResultTitle)) score += 8;
    else if (normalizedResultTitle.startsWith(text) && text.length >= 12) score += 7;
    else if (text.includes(normalizedResultTitle) || normalizedResultTitle.includes(text)) score += 6;
  }
  if (element.tagName === "H1") score += 4;
  if (element.tagName === "H2") score += 2;
  if (/jobpostingheader|jobtitle|job-title|posting-title|body--medium/.test(classText)) score += 3;
  if (top >= 0 && top < 900) score += 2;

  return score;
}

function findDetailTitleHost(result) {
  const resultTitle = result?.title || "";
  const selectors = [
    "main h1",
    "article h1",
    "h1",
    "main h2",
    "article h2",
    "h2",
    "[role='heading']",
    "main p[class*='body--medium']",
    "[class*='job-title']",
    "[class*='jobTitle']",
    "[class*='posting-title']",
    "[class*='jobPostingHeader']",
    "[data-testid*='title']",
  ];
  const candidates = Array.from(document.querySelectorAll(selectors.join(", ")))
    .filter(isElementVisible)
    .filter((element) => !isBadDetailTitleCandidate(element))
    .map((element) => ({
      element,
      score: scoreDetailTitleHost(element, resultTitle),
      top: element.getBoundingClientRect().top,
    }))
    .sort((left, right) => right.score - left.score || left.top - right.top);

  if (candidates[0]?.score > 0) {
    return candidates[0].element;
  }

  return null;
}

function ensureDetailCard(result, resolvedUrl) {
  const titleHost = findDetailTitleHost(result);
  const detailRoot = getDetailRoot();
  if (!(detailRoot instanceof HTMLElement)) {
    return;
  }

  const text = ageLabel(result?.likely_posted_date);
  const escapedUrl = CSS.escape(resolvedUrl);
  const existingCards = Array.from(
    document.querySelectorAll(`.howoldisthisjob-detail-card[data-howoldisthisjob-url="${escapedUrl}"]`)
  );
  const existing = existingCards[0] || null;
  for (const duplicate of existingCards.slice(1)) {
    duplicate.remove();
  }

  if (!text) {
    existing?.remove();
    return;
  }

  if (titleHost instanceof HTMLElement) {
    for (const badge of document.querySelectorAll(
      `.howoldisthisjob-age-badge[data-howoldisthisjob-context="detail"][data-howoldisthisjob-url="${escapedUrl}"]`
    )) {
      if (!titleHost.contains(badge)) {
        badge.remove();
      }
    }
    ensureBadge(titleHost, result, resolvedUrl, "detail");
    existing?.remove();
    return;
  }

  let card = existing;
  if (!(card instanceof HTMLElement)) {
    card = document.createElement("div");
    card.className = "howoldisthisjob-detail-card";
    card.dataset.howoldisthisjobUrl = resolvedUrl;
    card.innerHTML = `
      <img class="howoldisthisjob-detail-card__icon" src="${BADGE_LOGO_URL}" alt="" />
      <div class="howoldisthisjob-detail-card__body">
        <div class="howoldisthisjob-detail-card__title"></div>
        <div class="howoldisthisjob-detail-card__meta"></div>
      </div>
    `;
    if (titleHost instanceof HTMLElement) {
      titleHost.insertAdjacentElement("afterend", card);
    } else {
      detailRoot.insertAdjacentElement("afterbegin", card);
    }
  }

  const posted = formatDate(result?.likely_posted_date);
  const refreshed = formatDate(getRefreshDate(result));
  const title = card.querySelector(".howoldisthisjob-detail-card__title");
  const meta = card.querySelector(".howoldisthisjob-detail-card__meta");
  if (title instanceof HTMLElement) {
    title.textContent = posted ? `Originally posted ${posted}` : "Original posting date unavailable";
  }
  if (meta instanceof HTMLElement) {
    const parts = [];
    if (refreshed) {
      parts.push(`Last refreshed ${refreshed}`);
    }
    if (result?.confidence) {
      parts.push(`${result.confidence} confidence`);
    }
    parts.push(result?.platform || "job posting");
    meta.textContent = parts.join(" · ");
  }
  applyThemeAttribute(card);
}

function clearDetailCard(resolvedUrl) {
  const escapedUrl = CSS.escape(resolvedUrl);
  document
    .querySelectorAll(`.howoldisthisjob-detail-card[data-howoldisthisjob-url="${escapedUrl}"]`)
    .forEach((node) => node.remove());
  document
    .querySelectorAll(
      `.howoldisthisjob-age-badge[data-howoldisthisjob-context="detail"][data-howoldisthisjob-url="${escapedUrl}"]`
    )
    .forEach((node) => node.remove());
}

async function fetchChunk(urls) {
  if (urls.length === 0) return;

  urls.forEach((url) => PENDING_URLS.add(url));

  try {
    const response = await sendRuntimeMessage({
      type: "howoldisthisjob:batch-estimate",
      urls,
    });

    if (!response?.ok || !Array.isArray(response.results)) {
      throw new Error(
        response?.error || "Extension batch lookup failed because the background response was invalid."
      );
    }

    for (const item of response.results) {
      RESULT_CACHE.set(item.url, item);
    }
  } catch (error) {
    for (const url of urls) {
      RESULT_CACHE.set(url, {
        url,
        ok: false,
        error: error instanceof Error ? error.message : "Unknown extension error.",
      });
    }
  } finally {
    urls.forEach((url) => PENDING_URLS.delete(url));
  }
}

function nextListBatchUrls(orderedListUrls, anchorsByUrl) {
  return orderedListUrls
    .filter((url) => !RESULT_CACHE.has(url) && !PENDING_URLS.has(url))
    .filter((url) => hasNearViewportAnchor(anchorsByUrl.get(url) || []))
    .slice(0, LIST_FETCH_BATCH_SIZE);
}

async function fetchListUrls(urls) {
  await fetchChunk(urls).finally(() => {
    const refreshedAnchorsByUrl = collectAnchorsByUrl();
    renderListUrls(refreshedAnchorsByUrl, urls);
  });
}

function renderListUrls(anchorsByUrl, urls) {
  for (const url of urls) {
    const anchors = anchorsByUrl.get(url);
    if (!anchors) continue;

    const item = RESULT_CACHE.get(url);
    const result = item?.ok ? item.result : null;
    const isRenderable = result?.status === "success" && result?.likely_posted_date;

    for (const anchor of anchors) {
      if (isRenderable) {
        ensureBadge(getListBadgeHost(anchor), result, url, "list");
      } else {
        clearListBadge(anchor);
      }
    }
  }
}

function renderDetailUrl(detailUrl) {
  if (!detailUrl) return;

  const item = RESULT_CACHE.get(detailUrl);
  const result = item?.ok ? item.result : null;
  const isRenderable = result?.status === "success" && result?.likely_posted_date;

  if (isRenderable) {
    ensureDetailCard(result, detailUrl);
  } else {
    clearDetailCard(detailUrl);
  }
}

async function scanAndRender() {
  const detailUrl = resolveSupportedDetailUrl(window.location.href);
  renderDetailUrl(detailUrl);

  if (detailUrl) {
    if (!RESULT_CACHE.has(detailUrl) && !PENDING_URLS.has(detailUrl)) {
      await fetchChunk([detailUrl]);
      renderDetailUrl(detailUrl);
    }
    return;
  }

  while (true) {
    const anchorsByUrl = collectAnchorsByUrl();
    const orderedListUrls = prioritizeListUrls(anchorsByUrl);

    renderListUrls(anchorsByUrl, orderedListUrls);

    const nextUrls = nextListBatchUrls(orderedListUrls, anchorsByUrl);
    if (nextUrls.length === 0) {
      return;
    }

    await fetchListUrls(nextUrls);
    return;
  }
}

async function runScan() {
  if (scanInFlight) {
    rescanRequested = true;
    return;
  }

  scanInFlight = true;
  try {
    do {
      rescanRequested = false;
      await scanAndRender();
    } while (rescanRequested);
  } finally {
    scanInFlight = false;
  }
}

function scheduleScan() {
  if (scanTimer) {
    window.clearTimeout(scanTimer);
  }
  scanTimer = window.setTimeout(() => {
    scanTimer = null;
    runScan().catch((error) => {
      if (error instanceof Error && /Extension context invalidated/i.test(error.message)) {
        return;
      }
    });
  }, 120);
}

const observer = new MutationObserver(() => {
  scheduleScan();
});

observer.observe(document.documentElement, {
  childList: true,
  subtree: true,
});

window.addEventListener("scroll", scheduleScan, { passive: true });
window.addEventListener("resize", scheduleScan);

scheduleScan();
