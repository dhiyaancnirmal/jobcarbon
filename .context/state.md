# Repo State

## Current State
- Python CLI is implemented in a single `jobcarbon.py` file.
- Runtime dependencies zero; HTTP uses stdlib `urllib`, CLI uses stdlib `argparse`.
- HTTP retries transient failures with bounded exponential backoff; fails fast on 404 etc.
- Dependency-free HTTP API: `GET /healthz`, `GET /api/v1/estimate`, `POST /api/v1/estimate`, `GET /api/v1/platforms` with CORS.
- Added secure backend history APIs in `jobcarbon_api.py`: `GET /api/v1/history`, `POST /api/v1/history`, `DELETE /api/v1/history`, and `DELETE /api/v1/history/{id}`.
- Added SQLite persistence (stdlib `sqlite3`) for anonymous history sessions:
  - `anonymous_sessions` table (`id`, `cookie_token_hash`, `created_at`, `updated_at`)
  - `search_history` table (`id`, `session_id`, `created_at`, `url`, `result_json`)
  - index on `search_history(session_id, created_at DESC)`
- Added HttpOnly anonymous session cookie middleware for history routes:
  - cookie name `jobcarbon_session`
  - attributes: `HttpOnly`, `Secure`, `SameSite=None`, `Path=/`, `Max-Age=30d`
  - server stores only hashed cookie token; session lookup is server-side only
- CORS now uses strict allowlist (`JOBCARBON_ALLOWED_ORIGINS`, default localhost + production domains), supports credentials (`Access-Control-Allow-Credentials: true`), supports `DELETE`, and rejects disallowed origins with 403.
- SQLite DB path is configurable via `JOBCARBON_DB_PATH` (default `.tmp/jobcarbon.db`).
- Added frontend credentialed history fetches (`credentials: "include"`) in `site/src/lib/api.ts` so browser sends/receives HttpOnly session cookies.
- Railway deployment config present; API auto-binds to `0.0.0.0` when Railway injects `PORT`.
- GitHub Actions CI runs compile + unittest on pushes/PRs.
- Private GitHub repo at `dhiyaancnirmal/jobcarbon` on `main`.
- Railway hobby plan active at `https://jobcarbon-production.up.railway.app`.
- Custom domain `api.howoldisthisjob.com` attached to Railway (DNS verified).
- 60 tests passing (API history/session/CORS coverage plus ATS handlers, resolver-backed direct integrations, and platform capability coverage).

### Frontend
- Next.js 16.2.3 website at `site/` with Tailwind v4 and shadcn, Linear/Raycast aesthetic.
- Fonts: Inter (body) + JetBrains Mono (code).
- `site/` is tracked in main repo; `.gitignore` covers `node_modules`, `.next`, `.vercel`.
- Vercel project `jobcarbon-web` is connected to main repo.
- Layout: vh-anchored top padding `pt-[calc(50vh-7.125rem)]` on `<main>` so idle content is visually centered without reflow when `<details>` expands (no `justify-center`/`flex-1`). Pixel-verified (~0.19px off center at 633px viewport).
- Component set (rebuilt 2026-04-14): `JobChecker` wires `PlatformCarousel`, `Spinner` (scan preset), `SearchHistory`, `HistoryCard`, `ResultCard`, `ConfirmModal`, `PlatformDialog`.
- History persistence is now wired to the backend anonymous session store in `jobcarbon_api.py` via `site/src/lib/api.ts`:
  - `fetchHistory()` -> `GET /api/v1/history` with `credentials: "include"`
  - `saveToHistory()` -> `POST /api/v1/history`
  - `deleteHistoryItem()` -> `DELETE /api/v1/history/{id}`
  - `clearHistory()` -> `DELETE /api/v1/history`
  - frontend no longer uses `localStorage` for history; `site/src/lib/history.ts` was removed
- Homepage microcopy and `/about` FAQ now describe anonymous server-side history tied to an HttpOnly session cookie instead of claiming "No cookies" or browser-local storage.
- Homepage no longer shows any extra privacy/marketing microcopy under the input.
- Idle homepage layout no longer uses the `pt-[calc(50vh-7.125rem)]` centering hack; it now uses a simple viewport-height main area so the hero and footer fit without a scrollbar on first load.
- `html` uses `overflow-y: auto; scrollbar-gutter: stable` in `globals.css` to reserve scrollbar gutter space and prevent layout shift when content grows past the viewport (classic scrollbar systems only; overlay scrollbars are unaffected).
- Loading UI: submit button shows an inline spinner with the text "Checking…" while a request is in flight (replaced the opaque `gel-btn--loading` overlay that hid the button text behind a tiny spinner).
- Toasts (`site/src/components/toasts.tsx`) render top-right (`right-4 top-4`, `sm:right-6 sm:top-6`). Used for invalid-URL, fetch-error, and intercept notices. Auto-dismiss after 4500ms.
- `Logo` (`site/src/components/logo.tsx`) is a blank calendar — no day number rendered. Matches the favicon (`site/src/app/icon.svg`), which also has no number.
- `SearchHistory` result count reflects the filter: `"N results"` when unfiltered, `"N of M results"` when a filter is active.
- Result card simplified: removed redundant `result.summary` block and "Check again" button (semantically wrong — the original posting date shouldn't change).
- Slide-to-top animation on successful check: `<main>` transitions from `pt-[28vh]` to `pt-8` via `data-has-history` attribute; duration 500ms ease-out.
- Re-submitting a URL that already exists in history no longer re-fetches from the backend or creates a duplicate row. `JobChecker.onSubmit` matches the validated URL against existing `history` items and just expands the match; otherwise it runs a fresh check.
- Only `status === "success"` results are written to history. Non-success statuses (`blocked`, `unsupported`, `no_date`, `error`) surface as toasts instead of creating a history card. `ResultCard` still handles non-success statuses for legacy entries saved before this change.
- Toast messages simplified for bad inputs: "That doesn't look like a URL." (warn), "Couldn't reach that URL." (error) — no verbose titles or error.message bodies.
- Placeholder typing animation pauses whenever the input has text or a request is in flight, and successful submits keep the typed URL in the field instead of clearing it.
- Placeholder animation pause logic now depends on a single boolean (`placeholderAnimationPaused`) to avoid `useEffect` dependency-shape warnings during local dev refreshes.
- In local development, `site/src/lib/api.ts` defaults to `http://localhost:8000` when `NEXT_PUBLIC_JOBCARBON_API` is unset. Production still defaults to `https://api.howoldisthisjob.com`.
- Local dev services currently running under PM2:
  - `jobcarbon-site` -> Next dev server in `site/`
  - `jobcarbon-api` -> Python API on `http://127.0.0.1:8000`
- Pre-submit intercept dialogs fire for linkedin.com/jobs, indeed.com, careers.google.com, clearcompany/hrmdirect, workatastartup/ycombinator via `site/src/lib/platforms.ts`.
- `PlatformCarousel` + "23+ platforms supported" label appear only when `!hasHistory && !loading`; hidden after a result is saved.
- `ResultCard` defensively reads `warnings`, `all_dates`, `hidden_insights` with `?.` since mock/legacy history items may lack them.
- Layout includes footer with Home · About links + version `v0.2.0`; full OG/Twitter metadata + metadataBase in `layout.tsx`.
- `/about` page is back to a straightforward explainer layout: short intro, source list for "How it works", full platform status table, and FAQ cards. The brief redesign experiment was discarded.
- Backend history endpoints in `jobcarbon_api.py` are wired to the frontend history UI.

### Backend parity status
- Richer response schema: `status`, `likely_posted_date`, `chosen_source`, `all_dates`, `hidden_insights`, `warnings`
- Generic extractors: JSON-LD, metadata/regex, Open Graph, embedded JSON, Jina render, sitemap `lastmod`, Wayback
- Direct ATS fallbacks: Lever, Greenhouse, Ashby, SmartRecruiters, Workable, BambooHR, Brassring, SuccessFactors, Rippling, iCIMS, Dover, Workday (CXS), Oracle HCM, Jobvite, Avature, Gem, Teamtailor, Recruitee, Personio, Breezy HR, JazzHR / applytojob
- Blocked: Indeed, LinkedIn; Unsupported: Google Careers, ClearCompany / HRMDirect
- `PLATFORM_CAPABILITIES` registry powers `/api/v1/platforms` endpoint

## Next Steps
- Deploy backend changes to Railway and verify CORS allowlist/env values in deployed environment (if history backend is kept).
- Validate the deployed site against the deployed API to confirm cookie attributes and credentialed CORS behave correctly cross-origin, not just on localhost.
- Decide whether to keep the URL in the input after successful submit permanently, or clear it only after the response renders. Current behavior keeps it.
- Decide whether to remove the footer version string or align it with `site/package.json`; it still shows `v0.2.0` while the package version is `0.1.0`.
- Remaining parity backlog: ADP direct promotion, Paycor direct/title extraction. Keep employer-specific support as resolver logic, not as standalone platform taxonomy.
- Chrome extension: local JSON-LD detection first, then backend for ATS/archive fallbacks.
