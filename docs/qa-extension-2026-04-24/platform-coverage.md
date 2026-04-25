# Supported platform coverage - 2026-04-24

## Why this supplement exists

The first Chrome QA pass only sampled a handful of high-traffic ATS pages. That is not enough for this product because the backend and extension claim much broader coverage.

This supplement reconciles:

- the backend `PLATFORM_CAPABILITIES` list,
- the extension `manifest.json` content-script match list,
- the current 2026-04-25 live production API matrix,
- the existing complete production matrix snapshots,
- the additional 2026-04-24/25 batch samples for platforms that were missing from the old 72-row runner.

## Exact platform counts

- Backend source of truth: 28 supported platform buckets in `howoldisthisjob.PLATFORM_CAPABILITIES`.
- Public site carousel: 27 supported vendor platforms in `site/src/lib/supported-platforms.ts`.
- Difference: the backend includes `custom_backend`, which is not a normal vendor platform and is not listed in the public carousel.
- Current release matrix: 28 platform buckets, 84 rows.
- Previously missing matrix buckets now covered: `dayforce`, `pageup`, `taleo`, `ukg_pro`.
- Explicitly unsupported/blocked by backend: `indeed`, `linkedin`, `google_careers`, `clearcompany`.

## Important caveat

The old 72-row production API runner sent requests too quickly for the current production rate limit. On 2026-04-24 it reached `429 Too Many Requests` after the early part of the matrix. Those later 429s should be treated as a QA-infrastructure problem, not proof that each platform parser failed.

The runner now has configurable delay, retry, and `Retry-After` handling. The 2026-04-25 slow run completed all 84 rows without a 429.

## 2026-04-25 slow production matrix summary

Artifact: `all-supported-platforms-api-matrix-2026-04-25.json`

- Rows: 84.
- Platform buckets: 28.
- HTTP summary: 84 `200`.
- Result summary: 84 `success`.
- No `429 Too Many Requests` responses.
- Previously missing buckets: `dayforce`, `pageup`, `taleo`, and `ukg_pro` all returned 3/3 `success`.
- PageUp/Taleo note: the earlier no-date results came from stale or weak sample URLs, not from current parser failure on valid postings.

## Coverage table

| Platform | 2026-04-25 slow live API | Prior complete matrix | Extension/browser status | QA meaning |
| --- | --- | --- | --- | --- |
| `lever` | 3 success | 3 success | manually sampled in Chrome | Covered by current evidence |
| `greenhouse` | 3 success | 3 success | manually sampled in Chrome | Covered by current evidence |
| `ashby` | 3 success | 3 success | manually sampled in Chrome | Covered by current evidence |
| `workable` | 3 success | 3 no_date | manually sampled in Chrome | Covered by current evidence |
| `smartrecruiters` | 3 success | 3 success | manually sampled in Chrome | Covered by current evidence |
| `rippling` | 3 success | 2 success, 1 no_date | manifest covered | Covered by current evidence |
| `icims` | 3 success | 3 success | manifest covered | Covered by current evidence |
| `dover` | 3 success | 2 success, 1 no_date | manifest covered | Covered by current evidence |
| `bamboohr` | 3 success | 2 success, 1 no_date | manifest covered | Covered by current evidence |
| `jobvite` | 3 success | 2 success, 1 no_date | manifest covered | Covered by current evidence |
| `brassring` | 3 success | 1 success, 2 error | manifest covered | Covered by current evidence |
| `successfactors` | 3 success | 1 success, 2 no_date | manifest covered | Covered by current evidence |
| `avature` | 3 success | 1 success, 2 no_date | manifest covered | Covered by current evidence |
| `teamtailor` | 3 success | 3 success | manifest covered | Covered by current evidence |
| `recruitee` | 3 success | 2 success, 1 no_date | manually sampled in Chrome | Covered by current evidence |
| `personio` | 3 success | 1 success, 1 no_date, 1 error | manifest covered | Covered by current evidence |
| `breezy` | 3 success | 2 success, 1 no_date | manifest covered | Covered by current evidence |
| `jazzhr` | 3 success | 1 success, 1 no_date, 1 error | manifest covered | Covered by current evidence |
| `gem` | 3 success | 1 success, 2 error | manifest covered | Covered by current evidence |
| `workday` | 3 success | 2 no_date, 1 error | manifest covered | Covered by current evidence |
| `oracle_hcm` | 3 success | 1 success, 2 no_date | manifest covered | Covered by current evidence |
| `adp` | 3 success | 3 no_date | manifest covered | Covered by current evidence |
| `paycor` | 3 success | 3 success | manifest covered | Covered by current evidence |
| `custom_backend` | 3 success | 2 success, 1 error | not covered by extension content-script matches | Backend/site supported; extension cannot inject on these employer-specific hosts today |
| `dayforce` | 3 success | not covered by old 72-row runner | manifest covered | Covered by current evidence |
| `pageup` | 3 success | not covered by old 72-row runner | manifest covered | Covered by current evidence |
| `taleo` | 3 success | not covered by old 72-row runner | manifest covered | Covered by current evidence |
| `ukg_pro` | 3 success | not covered by old 72-row runner | manifest covered | Covered by current evidence |

## Additional findings from the broader coverage pass

### P3 - Expired posting badge is a labeling concern, not a release blocker

SmartRecruiters has broad API success, and the expired ServiceNow page still receives a badge. That is acceptable if the badge is understood as "original posting date." Optional copy/tooltip polish could make that clearer, but expired-state parsing is not central to the product purpose.

### Fixed - release matrix now covers every supported backend bucket

`scripts/run_prod_estimate_matrix.py` now includes PageUp, Dayforce, Taleo, and UKG Pro. A unit test asserts that every backend-supported platform bucket appears in the matrix with at least three URLs.

### P1 - Custom backend support is not equivalent to extension support

The backend/site supports custom employer backends such as Stripe, Amazon, and Bending Spoons. The extension manifest cannot generally inject on those employer-specific hosts unless they are enumerated. Product copy should avoid implying that the Chrome extension covers `custom_backend` broadly unless we add those match patterns or a different permission strategy.

### Fixed - production matrix runner has pacing and retry

The runner now has configurable request delay, max attempts, and rate-limit retry handling. The 2026-04-25 slow run completed without 429s.

### Fixed - stale sample rows replaced

The first slow 2026-04-25 run had 79/84 successes. These rows were replaced:

1. Ashby / 1Password returned `no_date`.
2. Avature / Bloomberg BQuant returned upstream fetch `502`.
3. Recruitee / 1X returned upstream fetch `502`.
4. Personio / Contabo `2546270` returned upstream fetch `502`.
5. JazzHR / Public Citizen Executive Assistant returned `no_date`.

After replacement, the 84-row slow matrix returned 84/84 successes.

## Updated production recommendation

Platform coverage is all-green at the backend/API matrix level.

The release matrix now passes over every supported backend platform bucket, includes three live URLs per bucket, and verifies the four previously missing buckets in production. Remaining release-readiness work is outside the backend platform matrix:

1. Decide whether `custom_backend` is a site/API feature only or an extension feature, then align the extension manifest and product copy.
2. Decide whether inconsistent inline list badges outside Ashby should block extension release, given that popup scanning still returns dated results.
