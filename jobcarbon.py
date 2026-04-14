from __future__ import annotations

import argparse
import json
import re
import socket
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from html import unescape
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/146.0.0.0 Safari/537.36"
)
DEFAULT_TIMEOUT_SECONDS = 15
MAX_HTTP_ATTEMPTS = 3
BACKOFF_BASE_SECONDS = 0.5
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
JSONLD_SCRIPT_RE = re.compile(
    r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
    re.IGNORECASE | re.DOTALL,
)


class DetectionError(Exception):
    """Base exception for user-facing detection failures."""


class InvalidURLError(DetectionError):
    """Raised when the CLI receives an invalid URL."""


class PageFetchError(DetectionError):
    """Raised when the primary job page could not be fetched."""


@dataclass
class URLMetadata:
    ats: str
    org: str | None = None
    job_id: str | None = None


class HTTPRequestError(Exception):
    """Raised when an HTTP request fails."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


@dataclass
class HTTPResponse:
    text: str
    status_code: int

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise HTTPRequestError(f"HTTP {self.status_code}")

    def json(self) -> Any:
        return json.loads(self.text)


class HTTPSession:
    def __init__(
        self,
        *,
        opener: Any = urlopen,
        sleeper: Any = time.sleep,
        max_attempts: int = MAX_HTTP_ATTEMPTS,
    ) -> None:
        self.headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
        }
        self.opener = opener
        self.sleeper = sleeper
        self.max_attempts = max_attempts

    def _backoff_seconds(self, attempt_number: int) -> float:
        return BACKOFF_BASE_SECONDS * (2 ** (attempt_number - 1))

    def get(self, url: str, timeout: int) -> HTTPResponse:
        request = Request(url, headers=self.headers)
        last_error: HTTPRequestError | None = None

        for attempt_number in range(1, self.max_attempts + 1):
            try:
                with self.opener(request, timeout=timeout) as response:
                    charset = response.headers.get_content_charset() or "utf-8"
                    body = response.read().decode(charset, errors="replace")
                    status_code = getattr(response, "status", response.getcode())
                    return HTTPResponse(text=body, status_code=status_code)
            except HTTPError as exc:
                last_error = HTTPRequestError(
                    f"{exc.code} {exc.reason} for url: {url}",
                    status_code=exc.code,
                    retryable=exc.code in RETRYABLE_STATUS_CODES,
                )
            except (URLError, TimeoutError, socket.timeout) as exc:
                reason = getattr(exc, "reason", exc)
                last_error = HTTPRequestError(
                    f"{reason} for url: {url}",
                    retryable=True,
                )

            if last_error is None:
                break

            if not last_error.retryable or attempt_number >= self.max_attempts:
                raise last_error

            self.sleeper(self._backoff_seconds(attempt_number))

        raise last_error or HTTPRequestError(f"Unknown request failure for url: {url}")


def build_session() -> HTTPSession:
    return HTTPSession()


def validate_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise InvalidURLError(f"Invalid URL: {url}")
    return url


def detect_ats(url: str) -> URLMetadata:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    segments = [segment for segment in parsed.path.split("/") if segment]

    if host == "jobs.lever.co" and len(segments) >= 2:
        return URLMetadata(ats="lever", org=segments[0], job_id=segments[1])

    if host in {"boards.greenhouse.io", "job-boards.greenhouse.io"}:
        try:
            jobs_index = segments.index("jobs")
        except ValueError:
            jobs_index = -1
        if jobs_index > 0 and len(segments) > jobs_index + 1:
            return URLMetadata(
                ats="greenhouse",
                org=segments[jobs_index - 1],
                job_id=segments[jobs_index + 1],
            )

    if host == "jobs.ashbyhq.com" and len(segments) >= 2:
        return URLMetadata(ats="ashby", org=segments[0], job_id=segments[1])

    return URLMetadata(ats="unknown")


def utc_today() -> date:
    return datetime.now(timezone.utc).date()


def normalize_date(value: Any) -> str | None:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 1_000_000_000_000:
            timestamp /= 1000.0
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).date().isoformat()

    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        if re.fullmatch(r"\d{13}", cleaned):
            return normalize_date(int(cleaned))
        if re.fullmatch(r"\d{10}", cleaned):
            return normalize_date(int(cleaned))
        if re.fullmatch(r"\d{8,14}", cleaned) and cleaned[:4].isdigit():
            if len(cleaned) >= 8:
                return f"{cleaned[:4]}-{cleaned[4:6]}-{cleaned[6:8]}"
        if cleaned.endswith("Z"):
            cleaned = cleaned[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(cleaned).date().isoformat()
        except ValueError:
            pass
        try:
            return date.fromisoformat(cleaned[:10]).isoformat()
        except ValueError:
            return None

    return None


def age_days(estimated_posted: str | None, today: date | None = None) -> int | None:
    if estimated_posted is None:
        return None
    reference_day = today or utc_today()
    posted_day = date.fromisoformat(estimated_posted)
    return (reference_day - posted_day).days


def evidence_item(source: str, field: str, value: Any, note: str | None = None) -> dict[str, Any]:
    item = {"source": source, "field": field, "value": value}
    if note:
        item["note"] = note
    return item


def normalize_result(
    *,
    url: str,
    ats: str,
    estimated_posted: str | None,
    confidence: str,
    method: str,
    evidence: list[dict[str, Any]],
    today: date | None = None,
) -> dict[str, Any]:
    return {
        "url": url,
        "ats": ats,
        "estimated_posted": estimated_posted,
        "confidence": confidence,
        "method": method,
        "age_days": age_days(estimated_posted, today=today),
        "evidence": evidence,
    }


def fetch_text(session: Any, url: str) -> str:
    response = session.get(url, timeout=DEFAULT_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.text


def fetch_json(session: Any, url: str) -> Any:
    response = session.get(url, timeout=DEFAULT_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def parse_jsonish(value: str) -> Any | None:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def extract_json_object_after_marker(text: str, marker: str) -> str | None:
    marker_index = text.find(marker)
    if marker_index == -1:
        return None

    start_index = text.find("{", marker_index)
    if start_index == -1:
        return None

    depth = 0
    in_string = False
    escaping = False

    for index in range(start_index, len(text)):
        character = text[index]
        if in_string:
            if escaping:
                escaping = False
            elif character == "\\":
                escaping = True
            elif character == '"':
                in_string = False
            continue

        if character == '"':
            in_string = True
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return text[start_index : index + 1]

    return None


def normalized_url_path(url: str) -> str:
    parsed = urlparse(url)
    return parsed.path.rstrip("/")


def is_job_posting(node: dict[str, Any]) -> bool:
    node_type = node.get("@type")
    if isinstance(node_type, list):
        return "JobPosting" in node_type
    return node_type == "JobPosting"


def iter_job_postings(node: Any) -> list[dict[str, Any]]:
    postings: list[dict[str, Any]] = []

    if isinstance(node, list):
        for item in node:
            postings.extend(iter_job_postings(item))
        return postings

    if not isinstance(node, dict):
        return postings

    if is_job_posting(node):
        postings.append(node)

    for key, value in node.items():
        if key in {"@graph", "mainEntity", "itemListElement", "subjectOf"}:
            postings.extend(iter_job_postings(value))

    return postings


def extract_job_postings_from_html(html: str) -> list[dict[str, Any]]:
    postings: list[dict[str, Any]] = []
    for raw_script in JSONLD_SCRIPT_RE.findall(html):
        parsed = parse_jsonish(unescape(raw_script.strip()))
        if parsed is None:
            continue
        postings.extend(iter_job_postings(parsed))
    return postings


def detect_from_jsonld(
    html: str,
    evidence: list[dict[str, Any]],
    today: date | None = None,
) -> dict[str, Any] | None:
    for posting in extract_job_postings_from_html(html):
        raw_date_posted = posting.get("datePosted")
        raw_valid_through = posting.get("validThrough")

        if raw_date_posted is not None:
            evidence.append(
                evidence_item("jsonld.jobposting", "datePosted", raw_date_posted)
            )
        if raw_valid_through is not None:
            evidence.append(
                evidence_item("jsonld.jobposting", "validThrough", raw_valid_through)
            )

        normalized = normalize_date(raw_date_posted)
        if normalized:
            return {
                "estimated_posted": normalized,
                "confidence": "high",
                "method": "jsonld.jobposting.datePosted",
                "today": today,
            }

    return None


def detect_from_lever(
    session: Any,
    metadata: URLMetadata,
    evidence: list[dict[str, Any]],
    today: date | None = None,
) -> dict[str, Any] | None:
    if not metadata.org or not metadata.job_id:
        return None

    api_url = (
        f"https://api.lever.co/v0/postings/{metadata.org}/{metadata.job_id}?mode=json"
    )
    try:
        payload = fetch_json(session, api_url)
    except HTTPRequestError as exc:
        evidence.append(
            evidence_item("lever.api", "error", str(exc), note="Lever API fallback failed")
        )
        return None

    raw_created = payload.get("createdAt")
    evidence.append(evidence_item("lever.api", "createdAt", raw_created))
    normalized = normalize_date(raw_created)
    if not normalized:
        return None

    return {
        "estimated_posted": normalized,
        "confidence": "high",
        "method": "lever.api.createdAt",
        "today": today,
    }


def detect_from_greenhouse(
    session: Any,
    html: str,
    original_url: str,
    metadata: URLMetadata,
    evidence: list[dict[str, Any]],
    today: date | None = None,
) -> dict[str, Any] | None:
    if not metadata.org or not metadata.job_id:
        return None

    api_url = (
        f"https://boards-api.greenhouse.io/v1/boards/{metadata.org}/jobs/{metadata.job_id}"
    )
    try:
        payload = fetch_json(session, api_url)
    except HTTPRequestError as exc:
        evidence.append(
            evidence_item(
                "greenhouse.api", "error", str(exc), note="Greenhouse API fallback failed"
            )
        )
        payload = None

    if payload is not None:
        first_published = payload.get("first_published")
        updated_at = payload.get("updated_at")
        if first_published is not None:
            evidence.append(
                evidence_item("greenhouse.api", "first_published", first_published)
            )
        if updated_at is not None:
            evidence.append(
                evidence_item(
                    "greenhouse.api",
                    "updated_at",
                    updated_at,
                    note="Greenhouse updated_at reflects edits or freshness, not original posting time.",
                )
            )

        normalized_first = normalize_date(first_published)
        if normalized_first:
            return {
                "estimated_posted": normalized_first,
                "confidence": "high",
                "method": "greenhouse.api.first_published",
                "today": today,
            }

        normalized_updated = normalize_date(updated_at)
        if normalized_updated:
            return {
                "estimated_posted": normalized_updated,
                "confidence": "medium",
                "method": "greenhouse.api.updated_at",
                "today": today,
            }

    return detect_from_greenhouse_html(
        html, original_url, metadata, evidence, today=today
    )


def extract_remix_context(html: str) -> Any | None:
    raw_object = extract_json_object_after_marker(html, "window.__remixContext")
    if raw_object is None:
        return None
    return parse_jsonish(raw_object)


def iter_greenhouse_jobs(node: Any) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []

    if isinstance(node, list):
        for item in node:
            jobs.extend(iter_greenhouse_jobs(item))
        return jobs

    if not isinstance(node, dict):
        return jobs

    if "absolute_url" in node and (
        "published_at" in node or "updated_at" in node or "id" in node
    ):
        jobs.append(node)

    for value in node.values():
        jobs.extend(iter_greenhouse_jobs(value))

    return jobs


def detect_from_greenhouse_html(
    html: str,
    original_url: str,
    metadata: URLMetadata,
    evidence: list[dict[str, Any]],
    today: date | None = None,
) -> dict[str, Any] | None:
    if not html:
        return None

    remix_context = extract_remix_context(html)
    if remix_context is None:
        return None

    target_path = normalized_url_path(original_url)
    for job in iter_greenhouse_jobs(remix_context):
        absolute_url = job.get("absolute_url") or ""
        job_id = str(job.get("id")) if job.get("id") is not None else None
        url_matches = absolute_url and normalized_url_path(absolute_url) == target_path
        id_matches = metadata.job_id is not None and metadata.job_id == job_id
        if not (url_matches or id_matches):
            continue

        published_at = job.get("published_at")
        updated_at = job.get("updated_at")
        if published_at is not None:
            evidence.append(
                evidence_item("greenhouse.html", "published_at", published_at)
            )
        if updated_at is not None:
            evidence.append(
                evidence_item(
                    "greenhouse.html",
                    "updated_at",
                    updated_at,
                    note="Greenhouse updated_at reflects edits or freshness, not original posting time.",
                )
            )

        normalized_published = normalize_date(published_at)
        if normalized_published:
            return {
                "estimated_posted": normalized_published,
                "confidence": "high",
                "method": "greenhouse.html.published_at",
                "today": today,
            }

        normalized_updated = normalize_date(updated_at)
        if normalized_updated:
            return {
                "estimated_posted": normalized_updated,
                "confidence": "medium",
                "method": "greenhouse.html.updated_at",
                "today": today,
            }

    return None


def detect_from_ashby(
    session: Any,
    original_url: str,
    metadata: URLMetadata,
    evidence: list[dict[str, Any]],
    today: date | None = None,
) -> dict[str, Any] | None:
    if not metadata.org or not metadata.job_id:
        return None

    api_url = f"https://api.ashbyhq.com/posting-api/job-board/{metadata.org}"
    try:
        payload = fetch_json(session, api_url)
    except HTTPRequestError as exc:
        evidence.append(
            evidence_item("ashby.api", "error", str(exc), note="Ashby API fallback failed")
        )
        return None

    jobs = payload.get("jobs", [])
    parsed_original = urlparse(original_url)
    target_path = parsed_original.path.rstrip("/")

    for job in jobs:
        job_url = (job.get("jobUrl") or "").strip()
        parsed_job_url = urlparse(job_url) if job_url else None
        published_value = job.get("publishedAt") or job.get("publishedDate")
        if not published_value:
            continue

        if job.get("id") == metadata.job_id:
            evidence.append(evidence_item("ashby.api", "publishedAt", published_value))
            normalized = normalize_date(published_value)
            if normalized:
                return {
                    "estimated_posted": normalized,
                    "confidence": "high",
                    "method": "ashby.api.publishedAt",
                    "today": today,
                }

        if parsed_job_url and parsed_job_url.path.rstrip("/") == target_path:
            evidence.append(evidence_item("ashby.api", "publishedAt", published_value))
            normalized = normalize_date(published_value)
            if normalized:
                return {
                    "estimated_posted": normalized,
                    "confidence": "high",
                    "method": "ashby.api.publishedAt",
                    "today": today,
                }

    return None


def detect_from_wayback(
    session: Any,
    url: str,
    evidence: list[dict[str, Any]],
    today: date | None = None,
) -> dict[str, Any] | None:
    api_url = (
        "https://web.archive.org/cdx/search/cdx"
        f"?url={url}&limit=1&output=json&fl=timestamp,original&filter=statuscode:200&sort=ascending"
    )
    try:
        payload = fetch_json(session, api_url)
    except HTTPRequestError as exc:
        evidence.append(
            evidence_item(
                "wayback.cdx", "error", str(exc), note="Wayback fallback failed"
            )
        )
        return None

    if not isinstance(payload, list) or len(payload) < 2:
        return None

    first_row = payload[1]
    if not first_row:
        return None

    timestamp = first_row[0]
    normalized = normalize_date(timestamp)
    evidence.append(
        evidence_item(
            "wayback.cdx",
            "first_snapshot",
            timestamp,
            note="Wayback first snapshot is a ceiling, not the true posted date.",
        )
    )
    if not normalized:
        return None

    return {
        "estimated_posted": normalized,
        "confidence": "low",
        "method": "wayback.first_snapshot_ceiling",
        "today": today,
    }


def analyze_url(
    url: str,
    *,
    session: Any | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    validated_url = validate_url(url)
    active_session = session or build_session()
    metadata = detect_ats(validated_url)
    evidence: list[dict[str, Any]] = []

    page_fetch_error: Exception | None = None
    html = ""
    try:
        html = fetch_text(active_session, validated_url)
    except HTTPRequestError as exc:
        page_fetch_error = exc
        evidence.append(
            evidence_item(
                "page.fetch",
                "error",
                str(exc),
                note="Primary page fetch failed; falling back to ATS and archive signals.",
            )
        )

    if html:
        jsonld_result = detect_from_jsonld(html, evidence, today=today)
        if jsonld_result:
            return normalize_result(
                url=validated_url,
                ats=metadata.ats,
                evidence=evidence,
                **jsonld_result,
            )

    fallback_result = None
    if metadata.ats == "lever":
        fallback_result = detect_from_lever(active_session, metadata, evidence, today=today)
    elif metadata.ats == "greenhouse":
        fallback_result = detect_from_greenhouse(
            active_session, html, validated_url, metadata, evidence, today=today
        )
    elif metadata.ats == "ashby":
        fallback_result = detect_from_ashby(
            active_session, validated_url, metadata, evidence, today=today
        )

    if fallback_result:
        return normalize_result(
            url=validated_url,
            ats=metadata.ats,
            evidence=evidence,
            **fallback_result,
        )

    wayback_result = detect_from_wayback(active_session, validated_url, evidence, today=today)
    if wayback_result:
        return normalize_result(
            url=validated_url,
            ats=metadata.ats,
            evidence=evidence,
            **wayback_result,
        )

    if page_fetch_error is not None:
        raise PageFetchError(f"Unable to fetch job page: {validated_url}") from page_fetch_error

    return normalize_result(
        url=validated_url,
        ats=metadata.ats,
        estimated_posted=None,
        confidence="unknown",
        method="unknown",
        evidence=evidence,
        today=today,
    )


def run_cli(url: str) -> int:
    try:
        result = analyze_url(url)
    except InvalidURLError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except PageFetchError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 3
    except Exception as exc:  # pragma: no cover - defensive CLI guard
        print(f"Error: Unexpected error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    return 0


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jobcarbon",
        description="Estimate how old a job posting really is.",
    )
    parser.add_argument("url", help="Job posting URL to inspect")
    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()
    raise SystemExit(run_cli(args.url))


if __name__ == "__main__":
    main()
