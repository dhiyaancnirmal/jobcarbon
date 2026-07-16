#!/usr/bin/env python3
"""Production /api/v1/estimate matrix: 3 employer URLs per supported ATS family."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.howoldisthisjob.com/api/v1/estimate"
REQUEST_DELAY_SECONDS = float(os.environ.get("HOWOLDISTHISJOB_MATRIX_DELAY_SECONDS", "2.0"))
MAX_ATTEMPTS = int(os.environ.get("HOWOLDISTHISJOB_MATRIX_MAX_ATTEMPTS", "3"))
RATE_LIMIT_RETRY_SECONDS = float(
    os.environ.get("HOWOLDISTHISJOB_MATRIX_RATE_LIMIT_RETRY_SECONDS", "30.0")
)

try:
    from scripts.ats_matrix import MATRIX
except ImportError:  # run directly as `python scripts/run_prod_estimate_matrix.py`
    from ats_matrix import MATRIX


def fetch(url: str, timeout: float = 120.0) -> tuple[int, dict]:
    q = f"{API}?url={urllib.parse.quote(url, safe='')}"
    req = urllib.request.Request(q, method="GET", headers={"User-Agent": "howoldisthisjob-matrix/1.0"})
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode()
                return resp.status, json.loads(body)
        except urllib.error.HTTPError as e:
            try:
                body = e.read().decode()
                payload = json.loads(body)
            except Exception:
                payload = {"error": {"message": str(e)}}
            if e.code == 429 and attempt < MAX_ATTEMPTS:
                retry_after = e.headers.get("Retry-After")
                try:
                    delay = float(retry_after) if retry_after else RATE_LIMIT_RETRY_SECONDS
                except ValueError:
                    delay = RATE_LIMIT_RETRY_SECONDS
                time.sleep(delay)
                continue
            return e.code, payload
        except Exception as e:
            return 0, {"error": {"message": str(e)}}
    return 0, {"error": {"message": "Request attempts exhausted."}}


def main() -> None:
    rows: list[dict] = []
    for index, (platform, employer, job_url) in enumerate(MATRIX):
        if index > 0 and REQUEST_DELAY_SECONDS > 0:
            time.sleep(REQUEST_DELAY_SECONDS)
        t0 = time.perf_counter()
        code, payload = fetch(job_url)
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        status = payload.get("status") if isinstance(payload, dict) else None
        plat = payload.get("platform") if isinstance(payload, dict) else None
        err = (payload.get("error") or {}).get("message") if isinstance(payload, dict) else None
        summary = (payload.get("summary") or "")[:120] if isinstance(payload, dict) else ""
        rows.append(
            {
                "matrix_platform": platform,
                "employer": employer,
                "url": job_url,
                "http": code,
                "result_status": status,
                "detected_platform": plat,
                "error": err,
                "summary_snip": summary,
                "elapsed_ms": elapsed_ms,
            }
        )
        print(json.dumps(rows[-1], ensure_ascii=False), flush=True)

    out_path = sys.argv[1] if len(sys.argv) > 1 else "matrix_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(rows)} rows to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
