# Head-to-Head: `howoldisthisjob.com` vs `whenthisjobwasposted.com`

Date run: April 21, 2026

Method:

- 1 current live public job URL per ATS family
- 23 ATS families total
- Excluded company-specific `custom_backend` cases like Stripe and Bending Spoons because they are not ATS categories
- Compared:
  - `https://api.howoldisthisjob.com/api/v1/estimate`
  - `https://whenthisjobwasposted.com`

Aggregate result:

- Ties: 17
- `howoldisthisjob.com` wins: 5
- `whenthisjobwasposted.com` wins: 1

Latency:

- `howoldisthisjob.com` median: 1.585s
- `whenthisjobwasposted.com` median: 8.774s
- `howoldisthisjob.com` mean: 3.212s
- `whenthisjobwasposted.com` mean: 9.725s

Notable wins for `howoldisthisjob.com`:

- Ashby: API-backed date beat the competitor's fresher page timestamp (`2026-04-13` vs `2026-04-14`)
- iCIMS: avoided a false older regex date (`2026-02-18` vs `2024-02-05`)
- Dover: competitor reported automated-access blocking; `howoldisthisjob.com` returned a date
- Recruitee: avoided over-trusting older sitemap/archive evidence (`2026-01-29` vs `2026-01-16`)
- ADP: API-backed date beat the competitor's stale regex date (`2026-04-15` vs `2026-04-08`)

Notable win for `whenthisjobwasposted.com`:

- Avature: `howoldisthisjob.com` only surfaced a Wayback ceiling (`2025-12-14`), while the competitor extracted `2024-08-05`

Notes:

- BambooHR had one transient `502` from `api.howoldisthisjob.com` during the first pass; a targeted rerun succeeded with the same date as the competitor.
- SuccessFactors and Paycor both produced usable dates on the competitor side, but its internal state still flagged them as `ats-no-date`; scoring here is based on extracted date presence, not that internal hint.
