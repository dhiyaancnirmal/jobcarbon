# jobcarbon

`jobcarbon` estimates how old a job posting really is by collecting multiple signals, classifying them, and choosing the oldest credible posted date.

Current backend layers:

- JSON-LD `JobPosting`
- page metadata and regex extraction
- Open Graph / article metadata
- embedded JSON / hydration payloads
- Direct ATS fallbacks for Lever, Greenhouse, Ashby, SmartRecruiters, Workable, BambooHR, Brassring, SAP SuccessFactors, Rippling, iCIMS, Dover, Workday (CXS), Oracle HCM (recruitingCEJobRequisitionDetails), Jobvite (CompanyJobs XML), Avature, Gem, Teamtailor, Recruitee, Personio, Breezy HR, and JazzHR / applytojob
- Direct domain-specific fallbacks for Amazon.jobs, Stripe careers, Goldman Sachs careers, and Bending Spoons
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
python3 jobcarbon.py https://jobs.lever.co/skio/bbdd5a7b-652a-43ad-b92e-58f4e970c694
```

Or install the console script locally:

```bash
pip install -e .
jobcarbon https://jobs.lever.co/skio/bbdd5a7b-652a-43ad-b92e-58f4e970c694
```

## HTTP API

Run the local API server:

```bash
python3 jobcarbon_api.py --host 127.0.0.1 --port 8000
```

Or via the console script after editable install:

```bash
jobcarbon-api --host 127.0.0.1 --port 8000
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

## Railway

This repo is set up for Railway with config-as-code in `railway.json`.

Deployment shape:

- Railway starts the API with `python3 jobcarbon_api.py`
- Railway provides `PORT`
- The API automatically binds to `0.0.0.0` when `PORT` is present
- Railway healthchecks use `GET /healthz`

Expected production topology:

- Website: `https://howoldisthisjob.com`
- API: `https://api.howoldisthisjob.com`

Suggested Railway flow:

1. Create a new Railway project from this repo.
2. Deploy the service as-is.
3. Add a custom domain for the API service, ideally `api.howoldisthisjob.com`.
4. Keep the website on its own service later, calling this API.

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
- Amazon.jobs `search.json?base_query={jobId}` fallback
- Stripe Greenhouse board fallback
- Goldman Sachs Oracle requisition-search fallback
- Bending Spoons MongoDB ObjectID timestamp fallback
- `/api/v1/platforms` capability endpoint
- Jina render fallback
- sitemap and Wayback comparison evidence
- blocked-platform behavior
