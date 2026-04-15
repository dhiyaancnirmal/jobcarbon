# Repo State

## Current State
- Python CLI is implemented in a single `jobcarbon.py` file.
- Runtime dependencies zero; HTTP uses stdlib `urllib`, CLI uses stdlib `argparse`.
- HTTP retries transient failures with bounded exponential backoff; fails fast on 404 etc.
- Dependency-free HTTP API: `GET /healthz`, `GET /api/v1/estimate`, `POST /api/v1/estimate`, `GET /api/v1/platforms` with CORS.
- Railway deployment config present; API auto-binds to `0.0.0.0` when Railway injects `PORT`.
- GitHub Actions CI runs compile + unittest on pushes/PRs.
- Private GitHub repo at `dhiyaancnirmal/jobcarbon` on `main`.
- Railway hobby plan active at `https://jobcarbon-production.up.railway.app`.
- Custom domain `api.howoldisthisjob.com` attached to Railway (DNS verified).
- 53 tests passing (ATS handlers, resolver-backed direct integrations, and platform capability coverage).

### Frontend
- Next.js 16.2.3 website at `site/` with Tailwind v4 and shadcn, Linear/Raycast aesthetic.
- Fonts: Inter (body) + JetBrains Mono (code).
- `site/` is tracked in main repo; `.gitignore` covers `node_modules`, `.next`, `.vercel`.
- Vercel project `jobcarbon-web` is now Git-connected to `https://github.com/dhiyaancnirmal/jobcarbon.git` from the `site/` root, so pushes on the repo can auto-deploy the website.
- Production alias `howoldisthisjob.com` was repointed from a stale early deployment to `dpl_Cw6CVKivvL5kx6CM54yLZ2pEzRrg` (`jobcarbon-2qe13elsi-dhiyaancnirmals-projects.vercel.app`), and the previous stale deployment was removed.
- After Git connection, the first auto-deploy failed because the Vercel project still had `rootDirectory = null`; patching the project to `rootDirectory = "site"` fixed Git-based production builds. The repaired production deployment is `dpl_GAfNpCi98cxVrYyju7xv8g2Wnamr`.
- Frontend age labels now derive from `likely_posted_date` in the browser's local calendar date instead of trusting the backend's UTC-based `likely_age_days`, which fixed "1 day old" appearing for same-day postings on April 14 local time.
- Ashby date selection now normalizes `publishedAt` into the page's declared timezone before comparing it to date-only page metadata. This fixes cases where Ashby exposes a UTC timestamp just after midnight that should still count as the previous local posting date.
- `site/src/lib/api.ts` has:
  - `EstimateResult` type matching backend `build_result` schema
  - `PlatformCapability` type and `PlatformsResponse` type matching `/api/v1/platforms`
  - `estimateJobAge()` and `fetchPlatforms()` functions
- `ResultCard` handles all backend statuses and fields (title, company, location, employment_type, reposted_likely, summary, chosen_source, all_dates, hidden_insights, warnings).
- Platform carousel expanded to **28 platforms** with unique brand-color gel buttons:
  - Direct: Lever, Greenhouse, Ashby, SmartRecruiters, Workable, Workday, BambooHR, Rippling, iCIMS, Oracle HCM, Jobvite, Brassring, SuccessFactors, Avature, Gem, Teamtailor, Recruitee, Personio, Breezy HR, JazzHR, Custom Employer Backend, Dover
  - Generic: ADP, Paycor
  - Carousel scrolls at 40s (doubled from 20s for more items)
- URL input placeholder cycles 10 example URLs across major platforms.
- Page shows "28+ platforms supported".
- `next build` and `npm run lint` pass clean.
- Vercel deployment at `howoldisthisjob.com`; `NEXT_PUBLIC_JOBCARBON_API` = `https://api.howoldisthisjob.com`.

### Backend parity status
- Richer response schema: `status`, `likely_posted_date`, `chosen_source`, `all_dates`, `hidden_insights`, `warnings`
- Generic extractors: JSON-LD, metadata/regex, Open Graph, embedded JSON, Jina render, sitemap `lastmod`, Wayback
- Direct ATS fallbacks: Lever, Greenhouse, Ashby, SmartRecruiters, Workable, BambooHR, Brassring, SuccessFactors, Rippling, iCIMS, Dover, Workday (CXS), Oracle HCM, Jobvite, Avature, Gem, Teamtailor, Recruitee, Personio, Breezy HR, JazzHR / applytojob
- Ashby handler prefers the localized API timestamp over date-only JSON-LD when they disagree by one day due to timezone conversion.
- Employer-specific URL resolvers collapse into underlying platforms (`greenhouse`, `oracle_hcm`) or a generic `custom_backend` bucket instead of surfacing employer names as first-class platforms.
- Blocked: Indeed, LinkedIn; Unsupported: Google Careers, ClearCompany / HRMDirect
- `PLATFORM_CAPABILITIES` registry powers `/api/v1/platforms` endpoint

## Next Steps
- Remaining parity backlog: ADP direct promotion, Paycor direct/title extraction. Keep employer-specific support as resolver logic, not as standalone platform taxonomy.
- If future live/site regressions appear, inspect the active Vercel deployment first before debugging application code; the main outage here was a stale production alias, not a dead backend.
- If the API keeps `likely_age_days`, treat it as UTC/server-centric metadata; user-facing website copy should continue to compute relative age from `likely_posted_date` on the client.
- If other ATSes expose full timestamps plus a board timezone, normalize those timestamps into the board timezone before comparing them to date-only metadata.
- Chrome extension: local JSON-LD detection first, then backend for ATS/archive fallbacks
- Commit and push the monorepo state
