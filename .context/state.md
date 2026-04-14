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
- Verified locally on 2026-04-14: `python3 -m unittest discover -s tests` passes (53 tests, incl. Workable, BambooHR, Brassring, SuccessFactors, Jobvite, Avature, Gem, Teamtailor, Recruitee, Personio XML fallback, Breezy HR, JazzHR, Amazon.jobs, Stripe, Goldman Sachs, Bending Spoons, Workday CXS, Oracle HCM, and platform capability coverage).

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
- Direct ATS fallbacks: Lever, Greenhouse, Ashby, SmartRecruiters, Workable, BambooHR, Brassring, SuccessFactors, Rippling, iCIMS, Dover, Workday (CXS), Oracle HCM, Jobvite, Avature, Gem, Teamtailor, Recruitee, Personio, Breezy HR, JazzHR / applytojob
- Direct domain-specific fallbacks: Amazon.jobs, Stripe careers, Goldman Sachs careers, Bending Spoons
- Workable fallback parses `window.jobBoard.initialState` → `data` with created/updated dates and department/workplace hidden insights
- BambooHR fallback calls `GET https://{company}.bamboohr.com/careers/{jobId}/detail` and reads `result.jobOpening.datePosted`
- Brassring fallback reads durable `<meta name="DC.Date">` plus `og:title` from the public job-details HTML
- SuccessFactors fallback promotes pages by HTML fingerprint (`j2w.init`, `rmkcdn.successfactors.com`, `ssoCompanyId`) and then checks `/services/rss/job/?locale=...&keywords={slug}`, with `itemprop=datePosted` as an additional durable fallback
- Rippling fallback uses live-verified `__NEXT_DATA__` payloads
- iCIMS fallback derives the internal API host from `<base href>` and queries `/api/jobs`
- Dover fallback calls `GET /api/v1/inbound/application-portal-job/{jobId}`
- Workday fallback calls `GET /wday/cxs/{tenant}/{site}/job/{jobPath}` and reads `jobPostingInfo.startDate`
- Oracle HCM fallback calls `GET /hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails?...finder=ById;Id="{reqId}",siteNumber={site}` and reads `items[0].ExternalPostedStartDate`
- Jobvite fallback scrapes `companyEId` from the public page config and calls `GET /CompanyJobs/Xml.aspx?c={companyEId}&j={jobId}`
- Avature fallback reads portal-specific RSS (`/{portal}/SearchJobs/feed/`) and sitemap indexes (`/{portal}/sitemap_index.xml`)
- Gem fallback calls `GET https://api.gem.com/job_board/v0/{board}/job_posts/` and reads `first_published_at`
- Verified live on 2026-04-14: `python3 jobcarbon.py https://jobs.gem.com/gem/4965519002` returns `gem.api.first_published_at` as the chosen durable source and still flags repost likelihood via newer `updated_at`.
- Teamtailor support relies on public page metadata (`article:published_time`) and JobPosting schema on `*.teamtailor.com/jobs/...` pages.
- Recruitee fallback calls `GET https://{company}.recruitee.com/api/offers/{slug}` and prefers `published_at`, with `updated_at` as refresh evidence.
- Personio support uses page JobPosting schema first and falls back to the public XML feed at `/xml?language=...` for `createdAt` when page dates are absent.
- Breezy HR fallback parses the public `data-position` payload and prefers `first_publish_date`, with `last_publish_date` as refresh evidence.
- JazzHR / applytojob support relies on public JobPosting JSON-LD on detail pages under `*.applytojob.com/apply/...`.
- Amazon.jobs fallback calls `GET https://www.amazon.jobs/en/search.json?base_query={jobId}` and reads `jobs[].posted_date`
- Stripe careers fallback maps `stripe.com/jobs/listing/.../{id}` to Stripe's public Greenhouse board API
- Goldman Sachs fallback maps `higher.gs.com/roles/{id}` to the public Oracle requisition-search endpoint on `hdpc.fa.us2.oraclecloud.com`
- Bending Spoons fallback derives the posted date from the MongoDB ObjectID embedded in `jobs.bendingspoons.com/positions/{objectid}`
- Generic `createdAt` extraction was downgraded because it produced false positives on live iCIMS pages
- ATS handlers now prefer their own title/company/location fields over weaker generic page-shell metadata
- Blocked platforms: Indeed, LinkedIn; Unsupported: Google Careers, ClearCompany / HRMDirect
- `PLATFORM_CAPABILITIES` registry powers the new `/api/v1/platforms` endpoint and exposes supported/direct/generic/blocked/unsupported counts.

## Next Steps
- Competitor parity audit on 2026-04-14 against `https://whenthisjobwasposted.com/about` is much closer now. Remaining product/backend gaps versus the competitor's current public claims are the genuinely unresolved public sources: ADP direct promotion and Paycor direct/title extraction path. Treat these as the active parity backlog before claiming full compatibility.
- Remaining ATS platforms (ADP, Paycor) still rely on generic extraction and archive/sitemap/render fallbacks. ADP’s public requisition endpoint is real, but one live sample probed on 2026-04-14 returned a sparse payload without `postDate` or title/location fields, so it should not be promoted until a second live sample confirms the durable payload shape. Paycor still only gives us title-level HTML without a durable posted date. Comeet remains a metadata-only candidate for later: the public careers page / script exposes canonical identifiers and freshness-style timestamps like `time_updated`, but not a durable original posting date.
- Decide whether local development should target the live API domain or restart a local `jobcarbon-api` PM2 process and point the site at it consistently
- Chrome extension: local JSON-LD detection first, then backend for ATS/archive fallbacks
- Competitor reverse-engineering on 2026-04-14: downloaded `https://whenthisjobwasposted.com/script.js?v=47` to `.tmp/competitor-script-v47.js` and mapped their actual architecture. The site is a single-file browser app that runs ATS detection client-side, uses a generic `fetchWithProxy(...)` wrapper (`proxy.whenthisjobwasposted.com` -> `corsproxy.io` -> `allorigins.win`) for most cross-origin reads, and only uses dedicated first-party proxy endpoints for the cases their browser could not call directly: `/gem-api` and `/bamboohr-api/{company}/{jobId}`. Confirmed platform handlers in their JS for Greenhouse, Ashby, Workable, Oracle HCM, Gem, BambooHR, Paycor, SuccessFactors RSS, Workday CXS, SmartRecruiters, Brassring, Lever, ADP Workforce Now, Rippling, Jobvite XML, iCIMS, Avature, plus domain-specific lookups for Amazon.jobs, Stripe, Goldman Sachs, and Bending Spoons, and early blocking/warning detection for Indeed, LinkedIn, Google Careers, ClearCompany/HRMDirect, and YC Work at a Startup.
- Add more gel button colors + carousel entries as new ATS platforms land
- Commit and push the now-clean monorepo state, including the tracked `site/` frontend
