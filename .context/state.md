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
