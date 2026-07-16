/// <reference types="@cloudflare/vitest-pool-workers" />

import {
  env,
  createExecutionContext,
  waitOnExecutionContext,
} from "cloudflare:test";
import { beforeEach, describe, expect, it, vi } from "vitest";
import worker, { ApiBackend } from "../src/index";

/**
 * The Cloudflare Worker entry point: howoldisthisjob production routing.
 *
 * Routing summary (see cloudflare/src/index.ts):
 *   /api/v1/history*  -> handled locally against D1 (handleHistoryRequest)
 *   /healthz | /api/v1/* -> proxied to a random `ApiBackend` container instance
 *                           via getRandom(env.API_BACKEND, INSTANCE_COUNT=2)
 *   anything else      -> 404 not_found
 *
 * The container-backed Durable Object (`ApiBackend extends Container`) cannot be
 * instantiated by miniflare (it needs a real container runtime). The proxy
 * routing decision (#7) is therefore exercised by calling `worker.fetch`
 * directly with a stub `API_BACKEND` binding that records the routing call,
 * rather than by standing up a real container. No production code is changed.
 */

type FetchHandler = (
  request: Request,
  env: Env,
  ctx: ExecutionContext,
) => Promise<Response>;
const fetch = worker.fetch as FetchHandler;

// ---------------------------------------------------------------------------
// D1 schema — copied VERBATIM from cloudflare/migrations/0001_history.sql.
// We apply it against the in-memory miniflare D1 binding so the worker sees the
// same tables it uses in production. It is not reinvented here.
// ---------------------------------------------------------------------------
const HISTORY_SCHEMA_SQL = `
CREATE TABLE IF NOT EXISTS anonymous_sessions (
  id TEXT PRIMARY KEY,
  cookie_token_hash TEXT UNIQUE NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS search_history (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  url TEXT NOT NULL,
  result_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_search_history_session_created_at
ON search_history (session_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_search_history_session_url
ON search_history (session_id, url);
`;

const BASE = "http://localhost/api/v1/history";
const WEB_ORIGIN = "http://localhost:3000";
const EXT_ORIGIN = "chrome-extension://efdbbcgmlpnildldcnalbdfhpndhmmcl";
const BAD_ORIGIN = "https://evil.example.com";

async function runSchema() {
  // D1's `.exec()` splits multi-statement SQL naively and breaks on
  // multi-line statements with parentheses; run each statement separately.
  for (const rawStmt of HISTORY_SCHEMA_SQL.split(";")) {
    const stmt = rawStmt.trim();
    if (stmt) {
      await env.HISTORY_DB.prepare(stmt).run();
    }
  }
}

beforeEach(async () => {
  await runSchema();
  await env.HISTORY_DB.prepare("DELETE FROM search_history").run();
  await env.HISTORY_DB.prepare("DELETE FROM anonymous_sessions").run();
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Invoke the worker's fetch handler with full control over env (for stubbing). */
async function callWorker(
  request: Request,
  envOverride: Partial<Env> = {},
): Promise<Response> {
  const ctx = createExecutionContext();
  const response = await fetch(
    request,
    { ...env, ...envOverride } as Env,
    ctx,
  );
  await waitOnExecutionContext(ctx);
  return response;
}

function historyRequest(
  method: string,
  body: unknown = undefined,
  opts: { origin?: string; cookie?: string; path?: string } = {},
): Request {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (opts.origin) headers["Origin"] = opts.origin;
  if (opts.cookie) headers["Cookie"] = opts.cookie;
  return new Request(opts.path ?? BASE, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
}

/** Extract the `name=value` portion of the session cookie from a Set-Cookie header. */
function extractSessionCookie(setCookie: string | null): string {
  expect(setCookie).toBeTruthy();
  const [nameValue] = setCookie!.split(";");
  return nameValue!.trim();
}

async function postHistory(
  url: string,
  result: Record<string, unknown>,
  cookie?: string,
  origin?: string,
): Promise<Response> {
  return callWorker(
    historyRequest("POST", { url, result }, { cookie, origin }),
  );
}

async function getHistory(cookie?: string, origin?: string): Promise<Response> {
  return callWorker(historyRequest("GET", undefined, { cookie, origin }));
}

async function deleteHistory(
  path: string,
  cookie?: string,
  origin?: string,
): Promise<Response> {
  return callWorker(
    historyRequest("DELETE", undefined, { cookie, origin, path }),
  );
}

async function historyCount(url: string, sessionId: string): Promise<number> {
  const row = await env.HISTORY_DB.prepare(
    "SELECT COUNT(*) AS n FROM search_history WHERE session_id = ? AND url = ?",
  )
    .bind(sessionId, url)
    .first<{ n: number }>();
  return row?.n ?? 0;
}

// ===========================================================================
// 1. History round-trip
// ===========================================================================
describe("history round-trip", () => {
  it("POST creates an item, issues a session cookie, GET returns it, DELETE removes it", async () => {
    const post = await postHistory(
      "https://example.com/job/1",
      { age_days: 42 },
    );
    expect(post.status).toBe(201);

    // CORS reflection for the (omitted) origin: nothing. We assert the session
    // cookie attributes here instead.
    const setCookie = post.headers.get("Set-Cookie");
    expect(setCookie).not.toBeNull();
    for (const attr of [
      "howoldisthisjob_session=",
      "HttpOnly",
      "Secure",
      "SameSite=None",
      "Path=/",
      "Max-Age=2592000",
    ]) {
      expect(setCookie).toContain(attr);
    }
    // HOWOLDISTHISJOB_COOKIE_DOMAIN is "" in the test config -> no Domain attr.
    expect(setCookie!.toLowerCase()).not.toContain("domain=");

    const created = (await post.json()) as { item: { id: string; url: string } };
    expect(created.item.id).toBeTruthy();
    expect(created.item.url).toBe("https://example.com/job/1");

    const cookie = extractSessionCookie(setCookie);

    // GET returns the created item.
    const get = await getHistory(cookie);
    expect(get.status).toBe(200);
    const { history } = (await get.json()) as {
      history: { id: string; url: string; result: Record<string, unknown> }[];
    };
    expect(history).toHaveLength(1);
    expect(history[0].id).toBe(created.item.id);
    expect(history[0].url).toBe("https://example.com/job/1");
    expect(history[0].result).toEqual({ age_days: 42 });

    // DELETE a single id removes it.
    const delOne = await deleteHistory(`${BASE}/${created.item.id}`, cookie);
    expect(delOne.status).toBe(204);
    const afterOne = await getHistory(cookie);
    expect(((await afterOne.json()) as { history: unknown[] }).history).toEqual(
      [],
    );
  });

  it("POSTing several items then full-clear DELETE empties history", async () => {
    const first = await postHistory("https://a.test/1", { n: 1 });
    const cookie = extractSessionCookie(first.headers.get("Set-Cookie"));
    await postHistory("https://a.test/2", { n: 2 }, cookie);
    await postHistory("https://a.test/3", { n: 3 }, cookie);

    const before = await getHistory(cookie);
    expect(((await before.json()) as { history: unknown[] }).history).toHaveLength(3);

    const cleared = await deleteHistory(BASE, cookie);
    expect(cleared.status).toBe(204);
    const after = await getHistory(cookie);
    expect(((await after.json()) as { history: unknown[] }).history).toEqual([]);
  });
});

// ===========================================================================
// 2. Session scoping
// ===========================================================================
describe("session scoping", () => {
  it("items created under one session are invisible to a different or absent cookie", async () => {
    const first = await postHistory("https://a.test/secret", { ok: true });
    const cookieA = extractSessionCookie(first.headers.get("Set-Cookie"));

    // A second, independent session creates a different item.
    const second = await postHistory("https://b.test/other", { ok: true });
    const cookieB = extractSessionCookie(second.headers.get("Set-Cookie"));
    expect(cookieA).not.toBe(cookieB);

    // Each session sees only its own item.
    const a = await getHistory(cookieA);
    const b = await getHistory(cookieB);
    expect(((await a.json()) as { history: { url: string }[] }).history.map((h) => h.url)).toEqual([
      "https://a.test/secret",
    ]);
    expect(((await b.json()) as { history: { url: string }[] }).history.map((h) => h.url)).toEqual([
      "https://b.test/other",
    ]);

    // No cookie at all -> empty list (no session can be resolved).
    const none = await getHistory();
    expect(((await none.json()) as { history: unknown[] }).history).toEqual([]);

    // A bogus cookie token -> empty list.
    const bogus = await getHistory("howoldisthisjob_session=totally-fake-token");
    expect(((await bogus.json()) as { history: unknown[] }).history).toEqual([]);
  });
});

// ===========================================================================
// 3. URL-dedupe upsert
// ===========================================================================
describe("url-dedupe upsert", () => {
  it("posting the same URL twice under one session yields a single updated row", async () => {
    const first = await postHistory("https://dup.test/x", { v: 1 });
    const cookie = extractSessionCookie(first.headers.get("Set-Cookie"));
    const firstItem = (await first.json()) as { item: { id: string } };

    const second = await postHistory("https://dup.test/x", { v: 2 }, cookie);
    expect(second.status).toBe(201);
    const secondItem = (await second.json()) as { item: { id: string } };

    // Same row id reused (upsert), not a duplicate.
    expect(secondItem.item.id).toBe(firstItem.item.id);

    // Resolve the session id from the DB to count rows directly.
    const sessionRow = await env.HISTORY_DB.prepare(
      "SELECT s.id AS sid FROM anonymous_sessions s JOIN search_history h ON h.session_id = s.id WHERE h.url = ? LIMIT 1",
    )
      .bind("https://dup.test/x")
      .first<{ sid: string }>();
    expect(sessionRow?.sid).toBeTruthy();
    expect(await historyCount("https://dup.test/x", sessionRow!.sid)).toBe(1);

    // The stored result reflects the latest write (v:2).
    const get = await getHistory(cookie);
    const { history } = (await get.json()) as {
      history: { result: Record<string, unknown> }[];
    };
    expect(history).toHaveLength(1);
    expect(history[0].result).toEqual({ v: 2 });
  });
});

// ===========================================================================
// 4. CORS
// ===========================================================================
describe("CORS", () => {
  it("reflects an allowed web origin with credentials", async () => {
    const res = await postHistory("https://c.test/1", { x: 1 }, undefined, WEB_ORIGIN);
    expect(res.headers.get("Access-Control-Allow-Origin")).toBe(WEB_ORIGIN);
    expect(res.headers.get("Access-Control-Allow-Credentials")).toBe("true");
    expect(res.headers.get("Vary")).toContain("Origin");
  });

  it("accepts an allowed chrome-extension origin", async () => {
    const res = await postHistory("https://c.test/2", { x: 2 }, undefined, EXT_ORIGIN);
    expect(res.headers.get("Access-Control-Allow-Origin")).toBe(EXT_ORIGIN);
    expect(res.headers.get("Access-Control-Allow-Credentials")).toBe("true");
  });

  it("rejects a disallowed origin with 403 and no allow-origin header", async () => {
    const res = await postHistory("https://c.test/3", { x: 3 }, undefined, BAD_ORIGIN);
    expect(res.status).toBe(403);
    expect(res.headers.get("Access-Control-Allow-Origin")).toBeNull();
    const body = (await res.json()) as { error: { code: string } };
    expect(body.error.code).toBe("cors_origin_not_allowed");
  });
});

// ===========================================================================
// 5. OPTIONS preflight
// ===========================================================================
describe("OPTIONS preflight", () => {
  it("returns 204 with the right headers for an allowed origin", async () => {
    const res = await callWorker(
      historyRequest("OPTIONS", undefined, { origin: WEB_ORIGIN }),
    );
    expect(res.status).toBe(204);
    expect(res.headers.get("Access-Control-Allow-Origin")).toBe(WEB_ORIGIN);
    expect(res.headers.get("Access-Control-Allow-Credentials")).toBe("true");
    expect(res.headers.get("Access-Control-Allow-Methods")).toBe(
      "GET, POST, DELETE, OPTIONS",
    );
    expect(res.headers.get("Access-Control-Allow-Headers")).toBe("Content-Type");
  });

  it("rejects preflight from a disallowed origin with 403", async () => {
    const res = await callWorker(
      historyRequest("OPTIONS", undefined, { origin: BAD_ORIGIN }),
    );
    expect(res.status).toBe(403);
    expect(res.headers.get("Access-Control-Allow-Origin")).toBeNull();
  });
});

// ===========================================================================
// 6. Unknown path -> 404
// ===========================================================================
describe("unknown path", () => {
  it("returns 404 not_found with no CORS allow header", async () => {
    const res = await callWorker(
      new Request("http://localhost/some/random/path", { method: "GET" }),
    );
    expect(res.status).toBe(404);
    expect(res.headers.get("Access-Control-Allow-Origin")).toBeNull();
    const body = (await res.json()) as { error: { code: string } };
    expect(body.error.code).toBe("not_found");
  });
});

// ===========================================================================
// 7. Proxy routing decision (container stub, no real container)
// ===========================================================================
describe("proxy routing to the container binding", () => {
  function makeBackendStub() {
    const fetchSpy = vi.fn(
      async (_req: Request) =>
        new Response("hello from container", {
          status: 200,
          headers: { "x-routed-by": "container-stub" },
        }),
    );
    const idFromNameSpy = vi.fn((name: string) => ({ name }));
    const getSpy = vi.fn((_id: unknown) => ({ fetch: fetchSpy }));
    const binding = {
      idFromName: idFromNameSpy,
      get: getSpy,
    };
    return { fetchSpy, idFromNameSpy, binding };
  }

  it("routes /api/v1/estimate POST to a random container instance and proxies the response", async () => {
    const { fetchSpy, idFromNameSpy, binding } = makeBackendStub();
    const request = new Request("http://localhost/api/v1/estimate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_url: "https://x.test/j" }),
    });
    const res = await callWorker(request, {
      API_BACKEND: binding as unknown as Env["API_BACKEND"],
    });

    expect(res.status).toBe(200);
    expect(await res.text()).toBe("hello from container");
    expect(res.headers.get("x-routed-by")).toBe("container-stub");
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    // getRandom(env.API_BACKEND, INSTANCE_COUNT=2) -> "instance-0" | "instance-1".
    const chosenName = idFromNameSpy.mock.calls[0]?.[0];
    expect(chosenName).toMatch(/^instance-[01]$/);
  });

  it("routes /healthz GET to the container binding", async () => {
    const { fetchSpy, binding } = makeBackendStub();
    const res = await callWorker(
      new Request("http://localhost/healthz", { method: "GET" }),
      { API_BACKEND: binding as unknown as Env["API_BACKEND"] },
    );
    expect(res.status).toBe(200);
    expect(await res.text()).toBe("hello from container");
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });

  it("does NOT route /api/v1/history to the container (served locally from D1)", async () => {
    const { fetchSpy, binding } = makeBackendStub();
    const res = await callWorker(
      historyRequest("GET"),
      { API_BACKEND: binding as unknown as Env["API_BACKEND"] },
    );
    // History is served locally; container is never consulted.
    expect(res.status).toBe(200);
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});

// Compile-time anchor: the exported class is the one wired in wrangler.jsonc.
void ApiBackend;
