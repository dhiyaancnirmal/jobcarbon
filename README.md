# howoldisthisjob

`howoldisthisjob` estimates how old a job posting really is by collecting multiple signals, classifying them, and choosing the oldest credible posted date.

Current backend layers:

- JSON-LD `JobPosting`
- page metadata and regex extraction
- Open Graph / article metadata
- embedded JSON / hydration payloads
- Direct ATS fallbacks for Lever, Greenhouse, Ashby, SmartRecruiters, Workable, BambooHR, Brassring, SAP SuccessFactors, Rippling, iCIMS, Dover, Workday (CXS), Oracle HCM (recruitingCEJobRequisitionDetails), Jobvite (CompanyJobs XML), Avature, Gem, Teamtailor, Recruitee, Personio, Breezy HR, and JazzHR / applytojob
- Employer-specific URL resolvers that map into underlying platforms or a generic `custom_backend` bucket
- Platform detection with generic/archival fallbacks for ADP Workforce Now and Paycor/Newton
- Unsupported / early-stop detection for ClearCompany / HRMDirect, Google Careers, Indeed, and LinkedIn
- Jina render fallback for JS-heavy pages
- sitemap `lastmod`
- Wayback first-seen archive ceiling

Blocked / limited handling:

- Indeed -> blocked
- LinkedIn -> blocked
- Google Careers -> detected, but no reliable date exposed

## CLI

```bash
python3 howoldisthisjob.py https://jobs.lever.co/skio/bbdd5a7b-652a-43ad-b92e-58f4e970c694
```

To install the console scripts in a repo-local virtualenv:

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -e .
./.venv/bin/howoldisthisjob https://jobs.lever.co/skio/bbdd5a7b-652a-43ad-b92e-58f4e970c694
```

## HTTP API

Run the local API server:

```bash
python3 howoldisthisjob_api.py --host 127.0.0.1 --port 8000
```

Or via the console script after editable install:

```bash
./.venv/bin/howoldisthisjob-api --host 127.0.0.1 --port 8000
```

Endpoints:

- `GET /healthz`
- `GET /api/v1/estimate?url=<job-url>`
- `POST /api/v1/estimate` with JSON body `{"url": "<job-url>"}`
- `GET /api/v1/platforms` — backend capability matrix (display name, supported flag, integration kind, detection patterns, notes) plus a summary count of direct vs generic vs blocked platforms

Response shape:

```json
{
  "url": "https://jobs.lever.co/acme/123",
  "normalized_url": "https://jobs.lever.co/acme/123",
  "platform": "lever",
  "status": "success",
  "title": "Software Engineer",
  "company": "Acme",
  "location": "Remote",
  "employment_type": "Full-time",
  "likely_posted_date": "2024-01-01",
  "likely_age_days": 10,
  "confidence": "high",
  "reposted_likely": false,
  "summary": "Oldest credible posted date is 2024-01-01 from jsonld.jobposting.datePosted.",
  "chosen_source": {
    "date": "2024-01-01",
    "source": "jsonld.jobposting",
    "field": "datePosted",
    "kind": "posted",
    "reliability": "high"
  },
  "all_dates": [],
  "hidden_insights": {},
  "warnings": []
}
```

## Cloudflare Deployment

This repo is set up to run the production API on Cloudflare:

- a Cloudflare Worker handles routing, CORS, and history endpoints
- a Cloudflare-managed container runs the existing Python API server
- D1 stores anonymous per-session search history
- the Worker is attached to `api.howoldisthisjob.com`

Expected production topology:

- Website: `https://howoldisthisjob.com`
- API: `https://api.howoldisthisjob.com`

CORS / cookie configuration:

- `HOWOLDISTHISJOB_ALLOWED_ORIGINS` controls allowed web origins for the Worker history routes.
- `HOWOLDISTHISJOB_ALLOWED_EXTENSION_ORIGINS` controls allowed Chrome extension origins for API and history routes. Keep both unpacked development IDs allowed while the old `jobcarbon` path is being phased out.
- the Python container keeps the same default allowlist used by the old Railway deployment path
- `HOWOLDISTHISJOB_COOKIE_DOMAIN` is optional; leaving it empty keeps the history cookie host-only on `api.howoldisthisjob.com`

Cloudflare files:

- Worker config: `wrangler.jsonc`
- Worker source: `cloudflare/src/index.ts`
- D1 schema: `cloudflare/migrations/0001_history.sql`
- Python container image: `Dockerfile.cloudflare`

Suggested Cloudflare flow:

1. `npm install`
2. `npm run cf:types`
3. `wrangler d1 execute howoldisthisjob-history --remote --file=cloudflare/migrations/0001_history.sql`
4. `npm run cf:deploy`

## Testing

```bash
python3 -m unittest discover -s tests -v
```

The current suite covers:

- platform detection
- JSON-LD extraction
- retry behavior
- date normalization
- evidence ranking / repost detection
- rich result contract
- Greenhouse API fallback
- SmartRecruiters API fallback
- Rippling embedded `__NEXT_DATA__` fallback
- iCIMS public `/api/jobs` fallback derived from the page's internal base host
- Dover application portal API fallback
- Workable embedded `window.jobBoard` payload fallback
- BambooHR `/careers/{jobId}/detail` JSON fallback
- Brassring `DC.Date` HTML metadata fallback
- SuccessFactors RSS + `itemprop=datePosted` fallback
- Workday CXS API fallback
- Oracle HCM recruitingCEJobRequisitionDetails fallback
- Jobvite `CompanyJobs/Xml.aspx` fallback
- Avature `SearchJobs/feed/` + portal sitemap fallback
- Gem `api.gem.com/job_board/v0/{board}/job_posts/` fallback
- Teamtailor public page metadata / JSON-LD fallback
- Recruitee `/api/offers/{slug}` fallback
- Personio page JSON-LD + `/xml?language=...` fallback
- Breezy HR `data-position` payload fallback
- JazzHR / applytojob JobPosting JSON-LD support
- Custom employer backend `search.json?base_query={jobId}` fallback
- Greenhouse resolver for employer-specific job URLs
- Oracle HCM resolver for employer-specific role URLs
- Custom employer backend ObjectID timestamp fallback
- `/api/v1/platforms` capability endpoint
- Jina render fallback
- sitemap and Wayback comparison evidence
- blocked-platform behavior
