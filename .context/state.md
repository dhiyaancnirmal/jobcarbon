# Repo State

## Current State
- Python CLI is implemented in a single `jobcarbon.py` file.
- Detection flow now prioritizes JSON-LD `JobPosting.datePosted`, then ATS-specific fallbacks for Lever, Greenhouse, Ashby, and SmartRecruiters, then Wayback as a ceiling.
- Runtime dependencies zero; HTTP uses stdlib `urllib`, CLI uses stdlib `argparse`.
- HTTP retries transient failures with bounded exponential backoff; fails fast on 404 etc.
- Dependency-free HTTP API: `GET /healthz`, `GET /api/v1/estimate`, `POST /api/v1/estimate` with CORS.
- Railway deployment config present; API auto-binds to `0.0.0.0` when Railway injects `PORT`.
- GitHub Actions CI runs compile + unittest on pushes/PRs.
- Private GitHub repo at `dhiyaancnirmal/jobcarbon` on `main`.
- Railway hobby plan active at `https://jobcarbon-production.up.railway.app`.
- Custom domain `api.howoldisthisjob.com` attached to Railway (DNS verified).
- Verified locally on 2026-04-14: `python3 -m unittest discover -s tests` passes (36 tests, incl. Workable extractor, Workday CXS, Oracle HCM, and platform capability coverage).

### Frontend
- Next.js 16.2.3 website at `site/` with Tailwind v4 and shadcn, Linear/Raycast aesthetic.
- Fonts: Inter (body) + JetBrains Mono (code).
- `site/` is now part of the main repo; the accidental nested git repo was removed on 2026-04-14.
- Root `.gitignore` now ignores frontend generated artifacts (`site/node_modules`, `site/.next`, `site/.vercel`) so the monorepo can track only source/config files.
- `site/src/lib/api.ts` updated to richer backend contract with full `EstimateResult` type.
- `ResultCard` **fully redesigned** to match new backend schema:
  - Maps to correct fields: `likely_age_days`, `likely_posted_date`, `platform`, `all_dates`
  - Handles non-success statuses: `blocked`, `unsupported`, `no_date` with distinct UI
  - Surfaces: `title`, `company`, `location`, `employment_type`, `reposted_likely` banner, `summary`, `chosen_source` with reliability dot, `hidden_insights` (collapsible), `warnings`
  - Evidence section shows all dates with kind labels, reliability dots, notes
- Platform carousel: Lever, Greenhouse, Ashby, **SmartRecruiters** with gel buttons in brand colors.
- SmartRecruiters gel button style added (red/pink gradient `#e04654` → `#c2185b`).
- URL input placeholder cycles through Lever, Greenhouse, Ashby, SmartRecruiters example URLs.
- `next build` passes clean.
- Verified on 2026-04-14: `https://howoldisthisjob.com` returns `200` from Vercel.
- `site/src/lib/api.ts` currently defaults to `https://api.howoldisthisjob.com`.
- `site/README.md` now reflects the actual frontend instead of the create-next-app boilerplate.

### Runtime Verification
- Verified on 2026-04-14: `https://api.howoldisthisjob.com/healthz` responds successfully.
- Verified on 2026-04-14: local PM2 process `jobcarbon-site` is online from `site/` and listening on `http://localhost:3000`.
- Verified on 2026-04-14: no local process is listening on `:8000`; there is no active local `jobcarbon-api` process right now.
- Verified on 2026-04-14: `npm run build` passes in `site/`.
- Verified on 2026-04-14: `npm run lint` passes in `site/` after removing a mount-only state effect from `PlatformCarousel`.

### Backend parity status
- Richer response schema: `status`, `likely_posted_date`, `chosen_source`, `all_dates`, `hidden_insights`, `warnings`
- Generic extractors: JSON-LD, metadata/regex, Open Graph, embedded JSON, Jina render, sitemap `lastmod`, Wayback
- Direct ATS fallbacks: Lever, Greenhouse, Ashby, SmartRecruiters, Workable, Rippling, iCIMS, Dover, Workday (CXS), Oracle HCM
- Workable fallback parses `window.jobBoard.initialState` → `data` with created/updated dates and department/workplace hidden insights
- Rippling fallback uses live-verified `__NEXT_DATA__` payloads
- iCIMS fallback derives the internal API host from `<base href>` and queries `/api/jobs`
- Dover fallback calls `GET /api/v1/inbound/application-portal-job/{jobId}`
- Workday fallback calls `GET /wday/cxs/{tenant}/{site}/job/{jobPath}` and reads `jobPostingInfo.startDate`
- Oracle HCM fallback calls `GET /hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails?...finder=ById;Id="{reqId}",siteNumber={site}` and reads `items[0].ExternalPostedStartDate`
- Generic `createdAt` extraction was downgraded because it produced false positives on live iCIMS pages
- ATS handlers now prefer their own title/company/location fields over weaker generic page-shell metadata
- Blocked platforms: Indeed, LinkedIn; Unsupported: Google Careers
- `PLATFORM_CAPABILITIES` registry powers the new `/api/v1/platforms` endpoint and exposes supported/direct/generic/blocked/unsupported counts.

## Next Steps
- Remaining ATS platforms (Jobvite, BambooHR, SuccessFactors, ADP, Brassring, Paycor, Avature) stay detection-only: no stable public payload was found on live pages during probing, and the repo rule is to avoid inventing endpoints
- Decide whether local development should target the live API domain or restart a local `jobcarbon-api` PM2 process and point the site at it consistently
- Chrome extension: local JSON-LD detection first, then backend for ATS/archive fallbacks
- Add more gel button colors + carousel entries as new ATS platforms land
- Commit and push the now-clean monorepo state, including the tracked `site/` frontend
