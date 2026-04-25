# Repo State

## Current State
- 2026-04-16: investigated Claude CLI startup config error shown in screenshot (`/Users/dhiyaan/.claude.json invalid JSON`).
  - Confirmed current `~/.claude.json` is parseable JSON (Python `json.loads` succeeds) with no BOM/NUL bytes.
  - Confirmed `claude` binary runs in this shell; current startup behavior is no longer JSON-parse failure.
  - Observed present CLI error is auth-related (`401 Invalid authentication credentials`) when invoking with `-p`, which indicates config parsing is no longer the blocker.
- 2026-04-16: fixed homepage motion/positioning behavior in the frontend.
  - `site/src/app/page.tsx` now animates `padding-top` (idle centered-ish -> top-anchored) instead of translating the whole content block, so the form moves upward immediately while loading (`data-has-history` includes loading state) and does not "snap" again after result render.
  - `site/src/components/result-card.tsx` replaced native `<details>` sections with controlled toggle buttons for Evidence/Hidden insights.
  - `site/src/components/history-card.tsx` removed the collapse button row that was contributing to jarring upward shifts; card stays expanded via parent state.
  - `site/src/components/logo.tsx` cleaned up stale day-number state/effect and now renders as a static blank calendar icon.
- Frontend verification:
  - `npm run lint` passes.
  - `npm run build` passes (Next.js 16.2.3).
- 2026-04-16 03:03 EDT: reliability backend changes were committed (`023ffa6`), pushed to `main`, and deployed to Railway production successfully.
- Deployment verification completed against `https://api.howoldisthisjob.com`:
  - `GET /healthz` returns `{ "ok": true, "service": "jobcarbon-api" }`.
  - iCIMS Peraton estimate now returns `status=success` with warning-level malformed JSON fallback message (no 500).
  - Additional production smoke checks: SuccessFactors `success`, Teamtailor `success`, Workday `no_date`, ADP `no_date`.
- 2026-04-16 backend reliability hardening is implemented and verified in `jobcarbon.py`, `jobcarbon_api.py`, and backend tests.
- Reliability changes now in code:
  - `fetch_json` hardens malformed/empty JSON payload handling and raises `HTTPRequestError` instead of leaking parser exceptions.
  - `analyze_url` runs extractors through `run_extraction_stage(...)`, so parser/extractor failures degrade to warnings instead of failing the request.
  - Added request-budget wiring (`RequestBudget`, `BudgetedSession`) and stage gating to reduce runaway fallback behavior.
  - `HTTPSession.get` now respects a per-call deadline and bounded backoff within that deadline.
  - Teamtailor detection now handles locale-prefixed `/jobs/...` and single-segment numeric-slug paths; Breezy detection supports `*.breezy.hr` subdomains.
  - API now maps `jobcarbon.HTTPRequestError` to `502` with `upstream_payload_error` in `jobcarbon_api.py`.
- Added/updated tests:
  - `tests/test_jobcarbon_unit.py`: Teamtailor single-segment path detection, BudgetedSession timeout floor behavior, comparison-evidence helper.
  - `tests/test_jobcarbon_integration.py`: malformed JSON degradation tests for iCIMS and Lever (no crash path).
  - `tests/test_jobcarbon_api.py`: mapping of analyzer `HTTPRequestError` to `upstream_payload_error`.
- Backend verification status:
  - `python3 -m unittest discover -s tests -v` passes (`68` tests).
  - Live ATS sweep executed against 24 ATS buckets/URLs (real company pages where available): `0` exceptions, `20` success, `4` no_date (Workday/ADP/Paycor/Workable edge case).
  - Repeated Peraton iCIMS checks now return success with warnings (no 500/parser crash).

## Recently Completed (2026-04-21)
- Bumped `site/` dependencies: `next` 16.2.3 → 16.2.4, `react`/`react-dom` 19.2.4 → 19.2.5, `eslint-config-next` 16.2.3 → 16.2.4. `npm install` + `npm run build` clean.
- Fixed Next.js 16 "scripts inside React components are never executed" error in `site/src/app/layout.tsx` by switching inline `<script dangerouslySetInnerHTML>` to `next/script` with `strategy="beforeInteractive"`.
- Fixed hydration mismatch: theme-init script was mutating `document.body.classList` before hydration but `<body>` lacked `suppressHydrationWarning`. Dropped the body toggle (Tailwind `dark:` reads from `<html>`) and added `suppressHydrationWarning` to `<body>` as belt-and-suspenders.
- Site history UX: multi-expand (expandedIds: Set<string> replacing single expandedId) + always-visible age chip on collapsed `history-card.tsx`.
- Chrome extension redesign shipped: outlined blue calendar logo, `float: right` placement into title whitespace, `width: max-content` fix for host flex-stretch, `chrome.storage.sync`-driven Light/Dark theme with popup toggle, default Light. 24/24 ATS smoke pass.
- Known open bugs: Breezy badge color leaks (host page CSS beats `!important` for fill/stroke), Recruitee detail badge lands over hero photo.

## In Progress
- Progress-pipeline visual polish per user feedback: removed uppercase tracking on the "Checking · {platform}" header (user rule: "NEVER do capitalized text"), tightened card padding (`p-4` → `px-3 py-2.5`), reduced inner gap (`gap-3` → `gap-2`), and tightened stage-row gap (`gap-1.5` → `gap-1`). User had two concerns: stage highlighting behavior was correct but visually undercooked, and vertical spacing felt too airy.
- Scrollbar-gutter fix in `globals.css` (third pass): Chrome still tinted the reserved gutter under the modal dim. Added custom scrollbar styling — `scrollbar-color: #d4d4d4 transparent` + WebKit rules making the track transparent and the thumb a rounded gray pill. Combined with `scrollbar-gutter: stable` + white html bg + modal overlay at `width: 100vw`, the gutter is now invisible on short pages and under the dim.

## Recently Completed (2026-04-16)
- Answered user question about Greenhouse original-date reliability. Root cause explained: public API only exposes `first_published` (scoped to current `job_id`) and `updated_at` (refresh); reposts mint new IDs and resets `first_published` with no cross-ID lineage in the payload. `detect_repost` at `jobcarbon.py:3079` and the UI warning ("Likely reposted — original listing may be older than shown") are the correct surfacing of this platform limitation. No code change made.
- Fixed layout shift: removed `padding-top` CSS transition animation from `page.tsx` `<main>`. Previously clicking "Check" triggered `data-has-history` (via loading state) which shifted entire content block upward by ~24vh. Now content stays fixed; results grow below. Also cleaned up `data-has-history` in `job-checker.tsx` to only set when history actually exists (not during loading).
- Redesigned `site/src/app/about/page.tsx`: replaced the verbose prose cards ("Signal order," "How to read a result") and the chip-grid supported-platforms section with a short hero + numbered 5-signals card + a **status table** (Supported/Blocked/No dates pills; driven by `SUPPORTED_PLATFORMS` plus hard-coded Indeed/LinkedIn = blocked and Google Careers/ClearCompany = unsupported, mirroring `jobcarbon.py` `BLOCKED_PLATFORM_MESSAGES`/`UNSUPPORTED_PLATFORM_MESSAGES`) + FAQ accordion with a chevron that rotates via Tailwind `group-open:rotate-180`. Lint clean; verified visually at 1280px via Playwright screenshot. User approved ("the about page is good").

## Open Design Thread
- User asked for ideas to hide perceived latency during a job-posting check. Two options surfaced:
  - Frontend-only: paced progress checklist mirroring the pipeline (Platform API → Metadata → Page → Sitemap → Archive).
  - Backend refactor: stream `/estimate` as SSE/chunked JSON so the frontend can show the real probe log (competitor-parity).
- No decision made yet; awaiting user pick.

## Next Steps
- If Claude still shows JSON parse errors interactively, replace `~/.claude.json` with a validated minimal config and re-authenticate.
- Optional: tighten soft budget behavior further (current per-call minimum timeout is small but non-zero).
- Optional: split matrix runner into strict real-job smoke set vs parser-probe set as previously recommended.

## Production-Readiness Backlog (2026-04-19)
User asked what's needed to reach "production level." Site + API are already live on Vercel / Railway; this is hardening work, not shipping. Gaps surfaced, priority order:

Blockers:
- 17 modified files tracked by git + untracked `site/src/components/progress-pipeline.tsx` — decide ship vs revert before new work layers on.
- No `/privacy` or `/terms` page; anonymous `jobcarbon_session` HttpOnly cookie needs disclosure.
- No rate limiting on `/api/v1/estimate` (public, upstream-amplifying).
- Missing `site/public/robots.txt` and `sitemap.xml` (metadata allows indexing, but discovery files are absent).

Reliability / observability:
- No error tracking (Sentry or equivalent) on `jobcarbon_api.py` or the Next site.
- No uptime monitoring / alerts beyond Railway `restartPolicyType: ON_FAILURE`.
- `.github/workflows/ci.yml` runs `py_compile + unittest` only — no frontend lint/build/test gate.
- No frontend tests (backend has 68).
- No security headers (CSP, HSTS, X-Frame-Options, Referrer-Policy) on either service.

Polish:
- No analytics on the site (no Vercel Analytics / Plausible wired up).
- No response cache for repeated URL lookups (`/api/v1/estimate` refetches each call).
- No recent a11y / Lighthouse pass.

Awaiting user pick on which slice to tackle first.

## Sentry Wiring (2026-04-19, in progress)
- Frontend: `@sentry/wizard` ran successfully under `site/`. Next.js project is `dhiyaan/jobcarbon`. Created `sentry.server.config.ts`, `sentry.edge.config.ts`, `src/instrumentation.ts`, `src/instrumentation-client.ts`, `src/app/global-error.tsx`. Wizard also added `withSentryConfig(...)` wrapper and `tunnelRoute: "/monitoring"` in `site/next.config.ts`.
- Wizard's example scaffolding (`src/app/sentry-example-page/`, `src/app/api/sentry-example-api/`) deleted.
- `tracesSampleRate` tuned from `1` → `0.1` in all three site configs to protect the 10k-performance-units/mo free quota.
- Backend: `jobcarbon_api.py` now performs a defensive `sentry_sdk.init(...)` from `SENTRY_DSN` env var with `traces_sample_rate=0.1` and `send_default_pii=True`. Added `_capture_exception` helper and wired it into the two `except Exception` fallbacks (sync handler ~line 519 and SSE stream handler ~line 589). Init is guarded so missing `sentry-sdk` or missing DSN is a no-op.
- `pyproject.toml` now depends on `sentry-sdk>=2.17`. Railway nixpacks will install it on next deploy.
- Local unit/integration/API suite still green (83 tests, up from 68 — the SSE stream endpoint shipped in the uncommitted-streaming commit added tests).
- `SENTRY_AUTH_TOKEN` pushed to Vercel **production** env (Preview skipped — CLI prompt wanted an additional "all preview branches" selection that didn't accept piped stdin cleanly; can add later if preview source-map upload becomes useful).
- Pending: user needs to create a **Python project** in the Sentry UI (name `jobcarbon-api`), then paste the DSN so we can run `railway variables --set SENTRY_DSN=...` and redeploy.
- Sentry MCP server explicitly declined by the user.

## Sentry Wiring (2026-04-19, completed)
- Created Sentry Python project `dhiyaan/jobcarbon-api` via REST API using a user-supplied broader auth token (the wizard's `SENTRY_AUTH_TOKEN` was scoped to source-map upload only).
- Backend DSN: `https://15bde52bdb02fa5ad72723bce3e13075@o4511248857235456.ingest.us.sentry.io/4511248942759936` (set as `SENTRY_DSN` on Railway, public DSN — fine to log).
- **Critical fix**: Railpack on Railway only detected Python and ran `python3 jobcarbon_api.py` directly — it did NOT run `pip install` from `pyproject.toml` alone. Added `requirements.txt` (single line: `sentry-sdk>=2.17`) which Railpack does pick up. New deploy installed `sentry-sdk-2.58.0` and healthcheck succeeded.
- Final state: both surfaces live with Sentry. Vercel production has `SENTRY_AUTH_TOKEN`; Railway has `SENTRY_DSN` + `SENTRY_ENVIRONMENT=production`. `/healthz` on `api.howoldisthisjob.com` returns OK after the requirements.txt redeploy. Commits: `36a227e` (Sentry wiring across both surfaces) and `5b38a98` (requirements.txt).

## SEO + Security headers + Analytics (2026-04-19, completed)
- `site/src/app/robots.ts`: app-router metadata file. Allow `/`, disallow `/monitoring` (Sentry tunnel) and `/api/`. Points crawlers at `https://howoldisthisjob.com/sitemap.xml`.
- `site/src/app/sitemap.ts`: lists `/`, `/about`, `/changelog`. Output verified to be valid `<urlset>` XML with `lastmod`, `changefreq`, `priority`.
- `site/next.config.ts`: added `headers()` returning 5 security headers globally (`source: '/:path*'`): `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy: camera=(), microphone=(), geolocation=(), browsing-topics=()`, `Content-Security-Policy: frame-ancestors 'none'`. Skipped a full script-src CSP because Sentry tunnel + Vercel Analytics + Tailwind would need nonce middleware — not worth the breakage risk for this scale. HSTS already comes from Vercel.
- `site/src/app/layout.tsx`: added `<Analytics />` from `@vercel/analytics/next` (v2.0.1) at end of `<body>`. Free tier, no config needed; data appears in Vercel dashboard once deployed.
- `npm run lint` clean, `npm run build` clean (8 static routes including `/robots.txt` and `/sitemap.xml`). Verified at `http://localhost:3001` after PM2 restart.

## Cloudflare Setup (2026-04-19, completed)
- Moved `howoldisthisjob.com` DNS from Spaceship to Cloudflare. Zone ID: `92a2115c6b80ea0b692f5052c38586eb`. Cloudflare nameservers: `gabriel.ns.cloudflare.com`, `saanvi.ns.cloudflare.com`. Zone active and proxying.
- All three DNS records proxied (orange cloud): `@` A 76.76.21.21 (Vercel), `www` A 76.76.21.21 (Vercel), `api` CNAME paig7uuj.up.railway.app (Railway). Verified apex + www still return 200 through the Cloudflare proxy with no Vercel TLS complaints.
- Rate limit rule created via Rulesets API (`http_ratelimit` phase) scoped to `http.host eq "api.howoldisthisjob.com" and starts_with(http.request.uri.path, "/api/v1/estimate")`. Characteristics: `ip.src + cf.colo.id`, period 10s, 10 req/period, action `block`, mitigation_timeout 10s. Free-plan entitlements force all three timers to 10s. Verified with a serial burst of 20: first 6 returned 400 (backend), remaining 14 returned 429 (Cloudflare block).
- User's Cloudflare plan is Workers Paid (account-scoped compute), but the jobcarbon zone sits on the Free zone plan — sufficient for this use case.
- API token `cfat_rXDRIgOIZyzfO3YPUCZ40iXgOa3JgqTbro6mIP4De074d911` updated by user on 2026-04-19 to add `Zone Settings:Edit`. Used the expanded scope to flip three zone settings: `always_use_https=on`, `automatic_https_rewrites=on`, `brotli=on`. Verified: `http://howoldisthisjob.com` now 301-redirects to `https://howoldisthisjob.com/`.
- Bot Fight Mode could NOT be flipped via API — the `/zones/{zone_id}/bot_management` endpoint requires Account-level Bot Management auth, not Zone Settings. User must toggle it manually at Security → Bots in the dashboard if desired (free, blocks obvious scrapers).
- No backend code change required — rate limiting lives at the edge.
