import { Container, getRandom } from "@cloudflare/containers";

const INSTANCE_COUNT = 2;
const SESSION_COOKIE_NAME = "howoldisthisjob_session";
const SESSION_MAX_AGE_SECONDS = 30 * 24 * 60 * 60;

const BASE_HEADERS: Record<string, string> = {
  "Content-Type": "application/json; charset=utf-8",
  "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
  "Cache-Control": "no-store",
  Vary: "Origin",
};

type ApiError = {
  error: {
    code: string;
    message: string;
  };
};

type HistoryItem = {
  id: string;
  created_at: string;
  url: string;
  result: Record<string, unknown>;
};

type SessionResolution = {
  sessionId: string | null;
  setCookie: string | null;
};

export class ApiBackend extends Container {
  defaultPort = 8080;
  sleepAfter = "15m";
  envVars = {
    PORT: "8080",
    PYTHONUNBUFFERED: "1",
    HOWOLDISTHISJOB_ALLOWED_EXTENSION_ORIGINS:
      "chrome-extension://efdbbcgmlpnildldcnalbdfhpndhmmcl,chrome-extension://nhaadlmaijnkebibldhidgdgghnehfea",
  };
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname.startsWith("/api/v1/history")) {
      return handleHistoryRequest(request, env, url);
    }

    if (url.pathname === "/healthz" || url.pathname.startsWith("/api/v1/")) {
      const containerInstance = await getRandom(env.API_BACKEND, INSTANCE_COUNT);
      return containerInstance.fetch(request);
    }

    return jsonResponse(
      { error: { code: "not_found", message: "Route not found." } },
      { status: 404 },
    );
  },
};

function jsonResponse(
  payload: Record<string, unknown>,
  init: ResponseInit = {},
): Response {
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json; charset=utf-8");
  }
  return new Response(JSON.stringify(payload, null, 2), {
    ...init,
    headers,
  });
}

function errorPayload(code: string, message: string): ApiError {
  return { error: { code, message } };
}

function parseCookieToken(cookieHeader: string | null): string | null {
  if (!cookieHeader) return null;
  for (const part of cookieHeader.split(";")) {
    const [rawName, ...rawValue] = part.trim().split("=");
    if (rawName !== SESSION_COOKIE_NAME) continue;
    const value = rawValue.join("=").trim();
    if (!value) return null;
    return decodeURIComponent(value);
  }
  return null;
}

function buildSessionCookie(token: string, env: Env): string {
  const parts = [
    `${SESSION_COOKIE_NAME}=${encodeURIComponent(token)}`,
    "HttpOnly",
    "Secure",
    "SameSite=None",
    "Path=/",
    `Max-Age=${SESSION_MAX_AGE_SECONDS}`,
  ];

  const cookieDomain = env.HOWOLDISTHISJOB_COOKIE_DOMAIN?.trim();
  if (cookieDomain) {
    parts.push(`Domain=${cookieDomain}`);
  }

  return parts.join("; ");
}

function utcNowIso(): string {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
}

function readAllowedOrigins(env: Env): Set<string> {
  const raw = env.HOWOLDISTHISJOB_ALLOWED_ORIGINS?.trim();
  if (!raw) {
    return new Set([
      "http://localhost:3000",
      "https://howoldisthisjob.com",
      "https://www.howoldisthisjob.com",
    ]);
  }

  return new Set(
    raw
      .split(",")
      .map((entry) => entry.trim())
      .filter(Boolean),
  );
}

function readAllowedExtensionOrigins(env: Env): Set<string> {
  const raw = env.HOWOLDISTHISJOB_ALLOWED_EXTENSION_ORIGINS?.trim();
  if (!raw) {
    return new Set([
      "chrome-extension://efdbbcgmlpnildldcnalbdfhpndhmmcl",
      "chrome-extension://nhaadlmaijnkebibldhidgdgghnehfea",
    ]);
  }

  const origins = new Set<string>();
  for (const entry of raw.split(",")) {
    const value = entry.trim();
    if (!value) continue;
    origins.add(
      value.startsWith("chrome-extension://")
        ? value
        : `chrome-extension://${value}`,
    );
  }
  return origins;
}

function buildCorsHeaders(request: Request, env: Env): {
  headers: Headers;
  origin: string | null;
  originAllowed: boolean;
} {
  const headers = new Headers(BASE_HEADERS);
  const origin = request.headers.get("Origin");
  if (!origin) {
    return { headers, origin: null, originAllowed: false };
  }

  const originAllowed =
    readAllowedOrigins(env).has(origin) ||
    (origin.startsWith("chrome-extension://") &&
      readAllowedExtensionOrigins(env).has(origin));

  if (originAllowed) {
    headers.set("Access-Control-Allow-Origin", origin);
    headers.set("Access-Control-Allow-Credentials", "true");
  }

  return { headers, origin, originAllowed };
}

async function sha256Hex(value: string): Promise<string> {
  const bytes = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

function randomToken(byteLength = 32): string {
  const bytes = crypto.getRandomValues(new Uint8Array(byteLength));
  let encoded = btoa(String.fromCharCode(...bytes));
  encoded = encoded.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
  return encoded;
}

async function resolveOrCreateSession(
  request: Request,
  env: Env,
  createIfMissing: boolean,
): Promise<SessionResolution> {
  const db = env.HISTORY_DB;
  if (!db) {
    return { sessionId: null, setCookie: null };
  }

  const cookieToken = parseCookieToken(request.headers.get("Cookie"));
  if (cookieToken) {
    const tokenHash = await sha256Hex(cookieToken);
    const row = await db
      .prepare(
        "SELECT id FROM anonymous_sessions WHERE cookie_token_hash = ? LIMIT 1",
      )
      .bind(tokenHash)
      .first<{ id: string }>();

    if (row?.id) {
      await db
        .prepare("UPDATE anonymous_sessions SET updated_at = ? WHERE id = ?")
        .bind(utcNowIso(), row.id)
        .run();
      return { sessionId: row.id, setCookie: null };
    }
  }

  if (!createIfMissing) {
    return { sessionId: null, setCookie: null };
  }

  const sessionId = crypto.randomUUID();
  const token = randomToken();
  const tokenHash = await sha256Hex(token);
  const now = utcNowIso();

  await db
    .prepare(
      "INSERT INTO anonymous_sessions (id, cookie_token_hash, created_at, updated_at) VALUES (?, ?, ?, ?)",
    )
    .bind(sessionId, tokenHash, now, now)
    .run();

  return {
    sessionId,
    setCookie: buildSessionCookie(token, env),
  };
}

function historyItemFromRow(row: {
  id: string;
  created_at: string;
  url: string;
  result_json: string;
}): HistoryItem {
  return {
    id: row.id,
    created_at: row.created_at,
    url: row.url,
    result: JSON.parse(row.result_json) as Record<string, unknown>,
  };
}

async function parseJsonBody(request: Request): Promise<Record<string, unknown>> {
  const payload = (await request.json()) as unknown;
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new Error("JSON body must be an object.");
  }
  return payload as Record<string, unknown>;
}

async function handleHistoryRequest(
  request: Request,
  env: Env,
  url: URL,
): Promise<Response> {
  const { headers, origin, originAllowed } = buildCorsHeaders(request, env);

  if (origin && !originAllowed) {
    return jsonResponse(errorPayload("cors_origin_not_allowed", "Origin is not allowed."), {
      status: 403,
      headers,
    });
  }

  if (request.method === "OPTIONS") {
    return new Response(null, { status: 204, headers });
  }

  const db = env.HISTORY_DB;
  if (!db) {
    return jsonResponse(
      errorPayload("history_store_unavailable", "History storage is not configured."),
      { status: 500, headers },
    );
  }

  const basePath = "/api/v1/history";
  let itemId: string | null = null;
  if (url.pathname !== basePath) {
    if (!url.pathname.startsWith(`${basePath}/`)) {
      return jsonResponse(errorPayload("not_found", "Route not found."), {
        status: 404,
        headers,
      });
    }
    itemId = decodeURIComponent(url.pathname.slice(basePath.length + 1).trim());
    if (!itemId) {
      return jsonResponse(errorPayload("not_found", "Route not found."), {
        status: 404,
        headers,
      });
    }
  }

  if (request.method === "GET") {
    if (itemId !== null) {
      return jsonResponse(errorPayload("method_not_allowed", "Use DELETE or OPTIONS."), {
        status: 405,
        headers,
      });
    }

    const { sessionId } = await resolveOrCreateSession(request, env, false);
    if (!sessionId) {
      return jsonResponse({ history: [] }, { status: 200, headers });
    }

    const result = await db
      .prepare(
        "SELECT id, created_at, url, result_json FROM search_history WHERE session_id = ? ORDER BY created_at DESC",
      )
      .bind(sessionId)
      .all<{
        id: string;
        created_at: string;
        url: string;
        result_json: string;
      }>();

    const seenUrls = new Set<string>();
    const history: HistoryItem[] = [];
    for (const row of result.results ?? []) {
      if (seenUrls.has(row.url)) continue;
      seenUrls.add(row.url);
      history.push(historyItemFromRow(row));
    }

    return jsonResponse({ history }, { status: 200, headers });
  }

  if (request.method === "POST") {
    if (itemId !== null) {
      return jsonResponse(errorPayload("method_not_allowed", "Use DELETE or OPTIONS."), {
        status: 405,
        headers,
      });
    }

    let payload: Record<string, unknown>;
    try {
      payload = await parseJsonBody(request);
    } catch {
      return jsonResponse(errorPayload("invalid_json", "Request body must be valid JSON."), {
        status: 400,
        headers,
      });
    }

    const rawUrl = payload.url;
    const result = payload.result;
    if (typeof rawUrl !== "string" || !rawUrl.trim()) {
      return jsonResponse(errorPayload("missing_url", "A non-empty 'url' value is required."), {
        status: 400,
        headers,
      });
    }
    if (!result || typeof result !== "object" || Array.isArray(result)) {
      return jsonResponse(
        errorPayload("missing_result", "A JSON object 'result' value is required."),
        { status: 400, headers },
      );
    }

    const { sessionId, setCookie } = await resolveOrCreateSession(request, env, true);
    if (!sessionId) {
      return jsonResponse(
        errorPayload("internal_error", "Unable to create a history session."),
        { status: 500, headers },
      );
    }

    const item: HistoryItem = {
      id: crypto.randomUUID(),
      created_at: utcNowIso(),
      url: rawUrl.trim(),
      result: result as Record<string, unknown>,
    };

    const existingRow = await db
      .prepare(
        "SELECT id FROM search_history WHERE session_id = ? AND url = ? ORDER BY created_at DESC LIMIT 1",
      )
      .bind(sessionId, item.url)
      .first<{ id: string }>();

    if (existingRow?.id) {
      item.id = existingRow.id;
      await db
        .prepare(
          "UPDATE search_history SET created_at = ?, url = ?, result_json = ? WHERE session_id = ? AND id = ?",
        )
        .bind(
          item.created_at,
          item.url,
          JSON.stringify(item.result),
          sessionId,
          item.id,
        )
        .run();
      await db
        .prepare("DELETE FROM search_history WHERE session_id = ? AND url = ? AND id != ?")
        .bind(sessionId, item.url, item.id)
        .run();
    } else {
      await db
        .prepare(
          "INSERT INTO search_history (id, session_id, created_at, url, result_json) VALUES (?, ?, ?, ?, ?)",
        )
        .bind(
          item.id,
          sessionId,
          item.created_at,
          item.url,
          JSON.stringify(item.result),
        )
        .run();
    }

    if (setCookie) {
      headers.set("Set-Cookie", setCookie);
    }

    return jsonResponse({ item }, { status: 201, headers });
  }

  if (request.method === "DELETE") {
    const { sessionId } = await resolveOrCreateSession(request, env, false);
    if (!sessionId) {
      return new Response(null, { status: 204, headers });
    }

    if (itemId === null) {
      await db
        .prepare("DELETE FROM search_history WHERE session_id = ?")
        .bind(sessionId)
        .run();
    } else {
      await db
        .prepare("DELETE FROM search_history WHERE session_id = ? AND id = ?")
        .bind(sessionId, itemId)
        .run();
    }

    return new Response(null, { status: 204, headers });
  }

  return jsonResponse(
    errorPayload("method_not_allowed", "Use GET, POST, DELETE, or OPTIONS."),
    { status: 405, headers },
  );
}
