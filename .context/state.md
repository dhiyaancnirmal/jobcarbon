# Repo State

## Current State
- Python CLI is implemented in a single `jobcarbon.py` file.
- Detection flow now prioritizes JSON-LD `JobPosting.datePosted`, then ATS-specific fallbacks for Lever, Greenhouse, and Ashby, then Wayback as a ceiling.
- Greenhouse has an extra HTML fallback that parses embedded `window.__remixContext` job data when the public boards API returns `404`.
- Runtime dependencies have been reduced to zero third-party packages; HTTP uses stdlib `urllib` and the CLI uses stdlib `argparse`.
- HTTP transport now retries transient failures with bounded exponential backoff for timeouts, connection issues, `429`, and `5xx`, while still failing fast on definitive errors like `404`.
- A dependency-free HTTP API wrapper now exists with `GET /healthz`, `GET /api/v1/estimate`, and `POST /api/v1/estimate`, including CORS headers for website and extension use.
- Railway deployment config is now present. The API auto-binds to `0.0.0.0` when Railway injects `PORT`, and `railway.json` declares the start command and healthcheck path.
- Local test suite and fixtures are present so default validation does not require network access.
- Live smoke validation succeeded on current Lever, Greenhouse, and Ashby job URLs.

## Next Steps
- Create the Railway service from this repo and attach a public domain, ideally `api.howoldisthisjob.com`.
- Website demo should call this hosted Python API as the source of truth.
- Chrome extension should perform local JSON-LD detection first for speed/privacy, then optionally call the hosted backend only for ATS and archive fallbacks.
- If reliability needs to go further, add request tracing or verbose diagnostics mode before adding more fallback complexity.
- When website work starts, keep the browser demo on the same origin as the API if possible, even though CORS is already supported.
