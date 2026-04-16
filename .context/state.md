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
- None.

## Recently Completed (2026-04-16)
- Fixed layout shift: removed `padding-top` CSS transition animation from `page.tsx` `<main>`. Previously clicking "Check" triggered `data-has-history` (via loading state) which shifted entire content block upward by ~24vh. Now content stays fixed; results grow below. Also cleaned up `data-has-history` in `job-checker.tsx` to only set when history actually exists (not during loading).

## Next Steps
- If Claude still shows JSON parse errors interactively, replace `~/.claude.json` with a validated minimal config and re-authenticate.
- Optional: tighten soft budget behavior further (current per-call minimum timeout is small but non-zero).
- Optional: split matrix runner into strict real-job smoke set vs parser-probe set as previously recommended.
