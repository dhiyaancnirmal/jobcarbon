# Chrome extension QA pass - 2026-04-24

## Scope

Manual QA was performed in Google Chrome with the installed `How Old Is This Job?` extension using the Computer Use / CUA MCP. The pass focused on whether the extension:

- injects on supported ATS pages,
- shows useful age badges or popup scan results,
- shows original posting dates consistently,
- has enough production confidence to continue toward release.

Screenshots are in `screenshots/`. The production API sample response is saved as `api-sample-results.json`.

See `platform-coverage.md` for the broader supported-platform reconciliation. The initial browser pass was intentionally visual, but it was not enough by itself because the product claims many more supported platforms than the handful sampled manually.

## Verdict

The backend platform matrix is all-green.

The extension mostly works on the manually sampled pages, and showing an original posting date on an expired job is consistent with the product purpose. The broader platform validation gap has been closed at the backend/API level: the automated release matrix now covers every backend-supported bucket and returns success for every row.

## Findings

### P3 - Expired SmartRecruiters detail page still gets an age badge

- URL: `https://jobs.smartrecruiters.com/ServiceNow/744000103790775-software-engineer`
- Evidence: `screenshots/08-smartrecruiters-servicenow-detail.png`
- Page state: visible page copy says `This job has expired`, and the apply CTA says `Sorry, this job has expired`.
- Extension state: inline age badge still appears beside the expired job title.
- API state: `api-sample-results.json` returns `status: success`, `likely_posted_date: 2026-02-13`, and no warning/closed-state marker for this URL.

Likely code path: `extension/content.js` renders both list and detail badges when `result.status === "success" && result.likely_posted_date`. This is acceptable if the badge means "original posting date" rather than "currently active job."

Optional polish:

1. Prefer tooltip/copy like `Originally posted Feb 13, 2026` on detail pages.
2. Do not block release solely because an expired page has a posting-date badge.

### P2 - Inline list badges are inconsistent outside Ashby

- Ashby/OpenAI list: inline badges render correctly.
- Greenhouse/Vercel list: popup finds and scans links, but no inline badges were visible in the list screenshot.
- Lever/Skio list: popup finds and scans links, but no inline badges were visible in the list screenshot.

Evidence:

- `screenshots/01-ashby-openai-list.png`
- `screenshots/04-greenhouse-vercel-list.png`
- `screenshots/05-greenhouse-vercel-popup-scanned.png`
- `screenshots/06-lever-skio-list.png`
- `screenshots/07-lever-skio-popup-scanned.png`

This is worth fixing before marketing the extension as list-page badge coverage across all supported ATS platforms because the popup scan still works and returns dated results, while inline list badges vary by ATS DOM.

### P3 - Popup scan can remain visually in a scanning state while showing results

Observed on Ashby and Greenhouse popup scans. The popup displayed dated results while the button/status still said `Scanning...` and `Querying ... posting dates...`.

Evidence:

- `screenshots/03-ashby-openai-popup-scanned.png`
- `screenshots/05-greenhouse-vercel-popup-scanned.png`

This may just be an in-progress capture during a long batch, but it should be checked with a completed scan state so the user does not interpret successful partial results as a hung scan.

## Site Matrix

| Site | URL | Current posting? | Extension result | Notes |
| --- | --- | --- | --- | --- |
| Ashby / OpenAI list | `https://jobs.ashbyhq.com/openai` | Yes, 655 open positions visible | Pass | Inline badges render; popup found 655 supported links and showed dated results. |
| Greenhouse / Vercel list | `https://job-boards.greenhouse.io/vercel` | Yes, 84 jobs visible | Partial | Popup found 50 supported links and returned dates; inline badges were not visible on the list page. |
| Lever / Skio list | `https://jobs.lever.co/skio` | Yes, active postings visible | Partial | Popup found 6 supported links and returned dates; inline badges were not visible on the list page. |
| SmartRecruiters / ServiceNow expired | `https://jobs.smartrecruiters.com/ServiceNow/744000103790775-software-engineer` | No, page says expired | Pass with labeling caveat | Extension showed the original posting-date badge. |
| SmartRecruiters / ServiceNow active | `https://jobs.smartrecruiters.com/ServiceNow/744000122552779--technical-lead-site-reliability-engineer-veza-` | Yes, `I'm interested` CTA visible | Pass | Inline detail badge showed `1d`; API returned Apr 23, 2026. |
| Workable / Jiffy | `https://apply.workable.com/jiffyshirts/j/5D4758376C/` | Yes | Pass | Detail page captured; API returned Mar 19, 2026. |
| Recruitee / McDugald Steele | `https://mcdugaldsteele.recruitee.com/o/project-landscape-architect-high-end-residential-design-build` | Yes | Pass | Detail badge shown; API flagged likely repost/refresh behavior. |

## Verification

- CUA-driven Chrome manual pass completed against the installed extension.
- Saved 11 screenshots in `docs/qa-extension-2026-04-24/screenshots/`.
- Saved live production batch API results in `docs/qa-extension-2026-04-24/api-sample-results.json`.
- Added the four previously missing matrix buckets: Dayforce, PageUp, Taleo, and UKG Pro.
- Added delay/retry/backoff to `scripts/run_prod_estimate_matrix.py`.
- Added a regression test that the production matrix covers every backend-supported platform bucket with at least three URLs.
- Ran focused local test suite with `uv run python -m unittest tests.test_howoldisthisjob_unit tests.test_howoldisthisjob_api`: 66 tests passed.
- Ran the slow 84-row production matrix on 2026-04-25: 28 platform buckets, 84 successes, 0 `no_date`, 0 upstream fetch failures, 0 rate-limit failures.
- Saved the slow matrix artifact in `docs/qa-extension-2026-04-24/all-supported-platforms-api-matrix-2026-04-25.json`.

## Production Recommendation

Continue product work. The expired-page badge is not a release blocker if the badge means original posting date, and the backend platform matrix is now green.

The broader platform pass adds the real release-readiness requirements:

1. Align `custom_backend` expectations: it is currently a backend/site capability, not broad Chrome-extension injection coverage.
2. Decide whether inconsistent inline list badges outside Ashby should block extension release, given that popup scanning still returns dated results.
