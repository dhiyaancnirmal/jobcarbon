# ATS Production Smoke Test — 2026-04-15

## Scope
- Environment: `https://howoldisthisjob.com` + `https://api.howoldisthisjob.com`
- Matrix size: 72 checks (24 ATS/platform buckets × 3 employer URLs each)
- Blocked platforms (Indeed/LinkedIn) excluded from success-path matrix

## Live website checks
- Performed on production UI in-browser with URL submit flow visible.
- Verified successful visible result for Lever/Plaid with summary: `Oldest credible posted date is 2026-02-27 from jsonld.jobposting.datePosted.`
- During a follow-up Workable submission, UI input remained temporarily disabled while request was in-flight; API run was used to complete full matrix coverage.

## Overall API outcome summary
- `200 + success`: 46 checks
- `200 + no_date`: 18 checks
- non-200 / parser errors: 8 checks

## Per-platform summary (3 employers each)

| Platform bucket | Success | No date | Errors |
|---|---:|---:|---:|
| adp | 0 | 3 | 0 |
| ashby | 3 | 0 | 0 |
| avature | 2 | 1 | 0 |
| bamboohr | 2 | 1 | 0 |
| brassring | 2 | 0 | 1 |
| breezy | 2 | 1 | 0 |
| custom_backend | 3 | 0 | 0 |
| dover | 2 | 1 | 0 |
| gem | 1 | 0 | 2 |
| greenhouse | 3 | 0 | 0 |
| icims | 2 | 0 | 1 |
| jazzhr | 2 | 0 | 1 |
| jobvite | 3 | 0 | 0 |
| lever | 3 | 0 | 0 |
| oracle_hcm | 1 | 2 | 0 |
| paycor | 0 | 3 | 0 |
| personio | 2 | 0 | 1 |
| recruitee | 2 | 1 | 0 |
| rippling | 3 | 0 | 0 |
| smartrecruiters | 3 | 0 | 0 |
| successfactors | 1 | 1 | 1 |
| teamtailor | 3 | 0 | 0 |
| workable | 1 | 2 | 0 |
| workday | 0 | 2 | 1 |

## Spot-checks for failures/timeouts

| Platform | Employer | URL | HTTP | Error |
|---|---|---|---:|---|
| icims | Peraton | https://careers-peraton.icims.com/jobs/164159/senior-ai-ml-engineer/job | 500 | Unexpected error: Expecting value: line 2 column 1 (char 2) |
| brassring | Brassring minimal | https://sjobs.brassring.com/TGnewUI/Search/home/HomeWithPreLoad?jobid=1&partnerid=1&siteid=1 | 502 | Unable to fetch job page: https://sjobs.brassring.com/TGnewUI/Search/home/HomeWithPreLoad?jobid=1&partnerid=1&siteid=1 |
| successfactors | SAP jobs | https://jobs.sap.com/job/Bangalore-Senior-Developer/1380193433/ | 0 | The read operation timed out |
| personio | Personio bad job | https://contabo.jobs.personio.de/job/99999999 | 502 | Unable to fetch job page: https://contabo.jobs.personio.de/job/99999999 |
| jazzhr | Applytojob board | https://acme.applytojob.com/apply/X/Y | 502 | Unable to fetch job page: https://acme.applytojob.com/apply/X/Y |
| gem | Gem root | https://jobs.gem.com/ | 502 | Unable to fetch job page: https://jobs.gem.com/ |
| gem | Gem acme | https://jobs.gem.com/acme/am9icG9zdDoxMjM | 502 | Unable to fetch job page: https://jobs.gem.com/acme/am9icG9zdDoxMjM |
| workday | Workday host | https://nvidia.wd5.myworkdayjobs.com/ | 502 | Unable to fetch job page: https://nvidia.wd5.myworkdayjobs.com/ |

## Notes
- Paycor public deep links are hard to source in the open web; detector was validated using `gnk=job&gni=...` query patterns (detected as `paycor`, returned `no_date`).
- Some rows intentionally probe host/root behavior for each platform family to observe parser fallback behavior, not just happy-path job pages.
- Raw results: `docs/ats-prod-matrix-results.json`
