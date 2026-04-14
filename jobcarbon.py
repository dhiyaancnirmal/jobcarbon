from __future__ import annotations

import argparse
import email.utils
import json
import re
import socket
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from html import unescape
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlparse
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
DATE_KIND_PRIORITY = {
    "posted": 0,
    "published": 1,
    "refresh": 2,
    "crawl": 3,
    "archive": 4,
    "expiry": 5,
    "unknown": 6,
}
RELIABILITY_PRIORITY = {"high": 0, "medium": 1, "low": 2}
SOURCE_PRIORITY = {
    "jsonld.jobposting": 0,
    "lever.api": 1,
    "greenhouse.api": 1,
    "greenhouse.html": 1,
    "ashby.api": 1,
    "smartrecruiters.api": 1,
    "workable.embedded": 1,
    "bamboohr.api": 1,
    "brassring.html": 1,
    "successfactors.rss": 1,
    "rippling.embedded": 1,
    "icims.api": 1,
    "dover.api": 1,
    "workday.cxs": 1,
    "oracle_hcm.api": 1,
    "jobvite.xml": 1,
    "avature.feed": 1,
    "avature.sitemap": 1,
    "gem.api": 1,
    "amazon_jobs.api": 1,
    "stripe.greenhouse": 1,
    "goldman_sachs.oracle": 1,
    "bendingspoons.objectid": 1,
    "open_graph": 2,
    "embedded.json": 3,
    "html.visible": 4,
    "html.regex": 5,
    "jina.render": 6,
    "sitemap": 7,
    "wayback.cdx": 8,
}
BLOCKED_PLATFORM_MESSAGES = {
    "indeed": "Indeed blocks automated access. Use the original company careers URL instead.",
    "linkedin": "LinkedIn blocks automated access. Use the original company careers URL instead.",
}
UNSUPPORTED_PLATFORM_MESSAGES = {
    "google_careers": "Google Careers does not expose reliable posting dates.",
    "clearcompany": "ClearCompany / HRMDirect career portals do not expose reliable posting dates.",
}
PLATFORM_CAPABILITIES = {
    "greenhouse": {
        "display_name": "Greenhouse",
        "supported": True,
        "integration": "direct",
        "detection": ["boards.greenhouse.io", "job-boards.greenhouse.io", "gh_jid"],
        "notes": "Public Greenhouse boards API plus embedded-board HTML fallback.",
    },
    "lever": {
        "display_name": "Lever",
        "supported": True,
        "integration": "direct",
        "detection": ["jobs.lever.co"],
        "notes": "Public Lever postings API.",
    },
    "ashby": {
        "display_name": "Ashby",
        "supported": True,
        "integration": "direct",
        "detection": ["jobs.ashbyhq.com", "ashby_jid"],
        "notes": "Ashby posting API lookup by board and job URL.",
    },
    "workable": {
        "display_name": "Workable",
        "supported": True,
        "integration": "direct",
        "detection": ["apply.workable.com", "jobs.workable.com/view"],
        "notes": "Embedded Workable jobBoard payload plus JSON-LD and generic fallbacks.",
    },
    "oracle_hcm": {
        "display_name": "Oracle HCM Cloud",
        "supported": True,
        "integration": "direct",
        "detection": ["*.oraclecloud.com/hcmUI"],
        "notes": "Public Oracle HCM `recruitingCEJobRequisitionDetails` REST endpoint with `ExternalPostedStartDate` as the posted date.",
    },
    "gem": {
        "display_name": "Gem",
        "supported": True,
        "integration": "direct",
        "detection": ["jobs.gem.com/{board}/{extId}"],
        "notes": "Public Gem Job Board API at `api.gem.com/job_board/v0/{board}/job_posts/` exposes `first_published_at`, location, departments, and employment metadata.",
    },
    "bamboohr": {
        "display_name": "BambooHR",
        "supported": True,
        "integration": "direct",
        "detection": ["*.bamboohr.com/careers"],
        "notes": "Public BambooHR `GET /careers/{jobId}/detail` JSON endpoint with `result.jobOpening.datePosted` as the posted date.",
    },
    "brassring": {
        "display_name": "Brassring",
        "supported": True,
        "integration": "direct",
        "detection": ["*.brassring.com", "jobid query param"],
        "notes": "Public Brassring job pages expose durable `DC.Date` metadata on the job-details HTML.",
    },
    "paycor": {
        "display_name": "Paycor / Newton",
        "supported": True,
        "integration": "generic",
        "detection": ["gnk=job", "gni query param", "newton.newtonsoftware.com", "recruitingbypaycor.com"],
        "notes": "Platform detection with generic extraction, sitemap, and archive fallbacks.",
    },
    "successfactors": {
        "display_name": "SAP SuccessFactors",
        "supported": True,
        "integration": "direct",
        "detection": ["successfactors in host or path", "j2w.init", "rmkcdn.successfactors.com", "ssoCompanyId"],
        "notes": "SuccessFactors-powered boards expose RSS search feeds at `/services/rss/job/` and often embed durable `itemprop=datePosted` metadata on the page.",
    },
    "workday": {
        "display_name": "Workday",
        "supported": True,
        "integration": "direct",
        "detection": ["*.myworkdayjobs.com"],
        "notes": "Public Workday CXS endpoint `/wday/cxs/{tenant}/{site}/job/{path}` with `jobPostingInfo.startDate` as the posted date.",
    },
    "smartrecruiters": {
        "display_name": "SmartRecruiters",
        "supported": True,
        "integration": "direct",
        "detection": ["jobs.smartrecruiters.com"],
        "notes": "Public SmartRecruiters posting API.",
    },
    "adp": {
        "display_name": "ADP Workforce Now",
        "supported": True,
        "integration": "generic",
        "detection": ["workforcenow.adp.com"],
        "notes": "Platform detection with generic extraction, sitemap, render, and archive fallbacks.",
    },
    "rippling": {
        "display_name": "Rippling",
        "supported": True,
        "integration": "direct",
        "detection": ["ats.rippling.com"],
        "notes": "Embedded __NEXT_DATA__ payload extraction.",
    },
    "jobvite": {
        "display_name": "Jobvite",
        "supported": True,
        "integration": "direct",
        "detection": ["jobs.jobvite.com", "CompanyJobs/Xml.aspx", "companyEId in page config"],
        "notes": "Public Jobvite XML feed `CompanyJobs/Xml.aspx?c={companyEId}&j={jobId}` with durable posting dates.",
    },
    "icims": {
        "display_name": "iCIMS",
        "supported": True,
        "integration": "direct",
        "detection": ["*.icims.com"],
        "notes": "Derived iCIMS API host plus /api/jobs pagination.",
    },
    "dover": {
        "display_name": "Dover",
        "supported": True,
        "integration": "direct",
        "detection": ["app.dover.com/apply"],
        "notes": "Public Dover application-portal job API.",
    },
    "avature": {
        "display_name": "Avature",
        "supported": True,
        "integration": "direct",
        "detection": ["*.avature.net", "avature.portal.id", "avacdn.net"],
        "notes": "Avature portals expose feed and sitemap data under `/{portal}/SearchJobs/feed/` and `/{portal}/sitemap_index.xml`.",
    },
    "amazon_jobs": {
        "display_name": "Amazon.jobs",
        "supported": True,
        "integration": "direct",
        "detection": ["www.amazon.jobs/en/jobs/{id}"],
        "notes": "Amazon's public `search.json?base_query={jobId}` endpoint returns durable `posted_date` and job metadata.",
    },
    "stripe": {
        "display_name": "Stripe Careers",
        "supported": True,
        "integration": "direct",
        "detection": ["stripe.com/jobs/listing/{slug}/{id}"],
        "notes": "Stripe career pages map to Stripe's public Greenhouse board API by job id.",
    },
    "goldman_sachs": {
        "display_name": "Goldman Sachs Careers",
        "supported": True,
        "integration": "direct",
        "detection": ["higher.gs.com/roles/{id}"],
        "notes": "Goldman role pages map to a public Oracle HCM requisition search endpoint keyed by role id.",
    },
    "bending_spoons": {
        "display_name": "Bending Spoons Jobs",
        "supported": True,
        "integration": "direct",
        "detection": ["jobs.bendingspoons.com/positions/{objectid}"],
        "notes": "Position URLs embed a MongoDB ObjectID whose timestamp yields the posted date.",
    },
    "indeed": {
        "display_name": "Indeed",
        "supported": False,
        "integration": "blocked",
        "detection": ["indeed.com"],
        "notes": BLOCKED_PLATFORM_MESSAGES["indeed"],
    },
    "linkedin": {
        "display_name": "LinkedIn",
        "supported": False,
        "integration": "blocked",
        "detection": ["linkedin.com/jobs"],
        "notes": BLOCKED_PLATFORM_MESSAGES["linkedin"],
    },
    "google_careers": {
        "display_name": "Google Careers",
        "supported": False,
        "integration": "unsupported",
        "detection": ["careers.google.com"],
        "notes": UNSUPPORTED_PLATFORM_MESSAGES["google_careers"],
    },
    "clearcompany": {
        "display_name": "ClearCompany / HRMDirect",
        "supported": False,
        "integration": "unsupported",
        "detection": ["*.hrmdirect.com"],
        "notes": UNSUPPORTED_PLATFORM_MESSAGES["clearcompany"],
    },
}
JSONLD_SCRIPT_RE = re.compile(
    r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
    re.IGNORECASE | re.DOTALL,
)
SCRIPT_JSON_BY_ID_RE = re.compile(
    r"<script[^>]+id=[\"'](?P<id>[^\"']+)[\"'][^>]*>(?P<body>.*?)</script>",
    re.IGNORECASE | re.DOTALL,
)
META_TAG_RE = re.compile(r"<meta\b([^>]+)>", re.IGNORECASE)
BASE_HREF_RE = re.compile(r"<base[^>]+href=[\"']([^\"']+)[\"']", re.IGNORECASE)
HTML_ATTR_RE = re.compile(r"([A-Za-z_:][A-Za-z0-9_:\-]*)\s*=\s*[\"'](.*?)[\"']")
VISIBLE_DATE_RE = re.compile(
    r"(?:(?:date\s+posted|posted|published|listing date|open date)\s*[:\-]?\s*)"
    r"([A-Z][a-z]{2,8}\s+\d{1,2},\s+\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})",
    re.IGNORECASE,
)
COMMON_DATE_PATTERNS = (
    ("datePosted", re.compile(r"datePosted[\"']?\s*[:=]\s*[\"']([^\"']+)[\"']", re.IGNORECASE), "posted", "high"),
    ("first_published", re.compile(r"first_published[\"']?\s*[:=]\s*[\"']([^\"']+)[\"']", re.IGNORECASE), "posted", "high"),
    ("published_at", re.compile(r"published_at[\"']?\s*[:=]\s*[\"']([^\"']+)[\"']", re.IGNORECASE), "published", "medium"),
    ("publishedAt", re.compile(r"publishedAt[\"']?\s*[:=]\s*[\"']([^\"']+)[\"']", re.IGNORECASE), "published", "medium"),
    ("createdAt", re.compile(r"createdAt[\"']?\s*[:=]\s*[\"']([^\"']+)[\"']", re.IGNORECASE), "posted", "low"),
    ("releasedDate", re.compile(r"releasedDate[\"']?\s*[:=]\s*[\"']([^\"']+)[\"']", re.IGNORECASE), "posted", "high"),
    ("updated_at", re.compile(r"updated_at[\"']?\s*[:=]\s*[\"']([^\"']+)[\"']", re.IGNORECASE), "refresh", "medium"),
    ("updatedAt", re.compile(r"updatedAt[\"']?\s*[:=]\s*[\"']([^\"']+)[\"']", re.IGNORECASE), "refresh", "medium"),
    ("validThrough", re.compile(r"validThrough[\"']?\s*[:=]\s*[\"']([^\"']+)[\"']", re.IGNORECASE), "expiry", "medium"),
)
DATE_KEY_RULES = {
    "dateposted": ("posted", "high"),
    "first_published": ("posted", "high"),
    "firstpublished": ("posted", "high"),
    "published_at": ("published", "medium"),
    "publishedat": ("published", "medium"),
    "publisheddate": ("published", "medium"),
    "releaseddate": ("posted", "high"),
    "createdat": ("posted", "low"),
    "updated_at": ("refresh", "medium"),
    "updatedat": ("refresh", "medium"),
    "lastmod": ("crawl", "low"),
    "validthrough": ("expiry", "medium"),
}
TEXT_TITLE_FIELDS = {"title", "name", "jobtitle"}
TEXT_COMPANY_FIELDS = {"company", "companyname", "hiringorganization", "organization", "accountname"}
TEXT_LOCATION_FIELDS = {"location", "fulllocation", "city", "region"}
TEXT_EMPLOYMENT_FIELDS = {"employmenttype", "typeofemployment", "employeetype", "workpersona"}
HIDDEN_INSIGHT_FIELDS = {
    "department",
    "team",
    "salary",
    "salaryrange",
    "basesalary",
    "compensation",
    "workplace",
    "workplace_type",
    "remote",
    "remote_type",
    "employmenttype",
    "typeofemployment",
    "employeetype",
    "workpersona",
    "requisitionid",
    "jobid",
    "jobadid",
    "refnumber",
    "identifier",
}
JINA_PREFIX = "https://r.jina.ai/http://"


class DetectionError(Exception):
    """Base exception for user-facing detection failures."""


class InvalidURLError(DetectionError):
    """Raised when the CLI receives an invalid URL."""


class PageFetchError(DetectionError):
    """Raised when no credible signal can be collected because fetches failed."""


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
            "Accept": "text/html,application/json;q=0.9,application/xml;q=0.8,*/*;q=0.7",
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


@dataclass
class URLMetadata:
    platform: str
    org: str | None = None
    job_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class CandidateDate:
    date: str
    source: str
    field: str
    kind: str
    reliability: str
    note: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "date": self.date,
            "source": self.source,
            "field": self.field,
            "kind": self.kind,
            "reliability": self.reliability,
        }
        if self.note:
            payload["note"] = self.note
        return payload


@dataclass
class AnalysisAccumulator:
    url: str
    normalized_url: str
    platform: str
    title: str | None = None
    company: str | None = None
    location: str | None = None
    employment_type: str | None = None
    warnings: list[str] = field(default_factory=list)
    all_dates: list[CandidateDate] = field(default_factory=list)
    hidden_insights: dict[str, Any] = field(default_factory=dict)

    def add_warning(self, message: str) -> None:
        if message not in self.warnings:
            self.warnings.append(message)

    def add_hidden(self, key: str, value: Any) -> None:
        if value in (None, "", [], {}):
            return
        if key not in self.hidden_insights:
            self.hidden_insights[key] = value

    def set_if_missing(self, field_name: str, value: Any) -> None:
        if value in (None, "", [], {}):
            return
        if getattr(self, field_name) in (None, ""):
            setattr(self, field_name, str(value).strip())

    def set_preferred(self, field_name: str, value: Any) -> None:
        if value in (None, "", [], {}):
            return
        setattr(self, field_name, str(value).strip())

    def add_date(
        self,
        raw_value: Any,
        *,
        source: str,
        field: str,
        kind: str,
        reliability: str,
        note: str | None = None,
    ) -> None:
        normalized = normalize_date(raw_value)
        if not normalized:
            return
        candidate = CandidateDate(
            date=normalized,
            source=source,
            field=field,
            kind=kind,
            reliability=reliability,
            note=note,
        )
        if not any(existing.as_dict() == candidate.as_dict() for existing in self.all_dates):
            self.all_dates.append(candidate)


def build_session() -> HTTPSession:
    return HTTPSession()


def validate_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise InvalidURLError(f"Invalid URL: {url}")
    return url


def build_normalized_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.scheme}://{parsed.netloc.lower()}{path}"


def detect_platform(url: str) -> URLMetadata:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    segments = [segment for segment in parsed.path.split("/") if segment]
    query = parse_qs(parsed.query)

    if "indeed.com" in host:
        return URLMetadata(platform="indeed")
    if host == "linkedin.com" or host.endswith(".linkedin.com"):
        return URLMetadata(platform="linkedin")
    if host == "careers.google.com":
        return URLMetadata(platform="google_careers")
    if host.endswith(".hrmdirect.com"):
        return URLMetadata(platform="clearcompany")
    if host == "www.amazon.jobs":
        job_match = re.search(r"/jobs/(\d+)", parsed.path, re.IGNORECASE)
        return URLMetadata(platform="amazon_jobs", job_id=job_match.group(1) if job_match else None)
    if host == "stripe.com" and "/jobs/listing/" in parsed.path:
        job_match = re.search(r"/jobs/listing/[^/]+/(\d+)", parsed.path, re.IGNORECASE)
        return URLMetadata(platform="stripe", job_id=job_match.group(1) if job_match else None)
    if host == "higher.gs.com" and "/roles/" in parsed.path:
        job_match = re.search(r"/roles/(\d+)", parsed.path, re.IGNORECASE)
        return URLMetadata(platform="goldman_sachs", job_id=job_match.group(1) if job_match else None)
    if host == "jobs.bendingspoons.com":
        job_match = re.search(r"/positions/([a-f0-9]{24})", parsed.path, re.IGNORECASE)
        return URLMetadata(platform="bending_spoons", job_id=job_match.group(1) if job_match else None)
    if host == "app.dover.com" and len(segments) >= 3 and segments[0] == "apply":
        return URLMetadata(platform="dover", org=segments[1], job_id=segments[2])
    if host == "jobs.lever.co" and len(segments) >= 2:
        return URLMetadata(platform="lever", org=segments[0], job_id=segments[1])
    if host in {"boards.greenhouse.io", "job-boards.greenhouse.io"}:
        try:
            jobs_index = segments.index("jobs")
        except ValueError:
            jobs_index = -1
        if jobs_index > 0 and len(segments) > jobs_index + 1:
            return URLMetadata(
                platform="greenhouse",
                org=segments[jobs_index - 1],
                job_id=segments[jobs_index + 1],
            )
        return URLMetadata(platform="greenhouse")
    if host == "jobs.ashbyhq.com" and len(segments) >= 2:
        return URLMetadata(platform="ashby", org=segments[0], job_id=segments[1])
    if host == "jobs.smartrecruiters.com" and len(segments) >= 2:
        job_id_match = re.match(r"(\d+)", segments[1])
        return URLMetadata(
            platform="smartrecruiters",
            org=segments[0],
            job_id=job_id_match.group(1) if job_id_match else segments[1],
        )
    if host == "apply.workable.com":
        job_id = segments[2] if len(segments) >= 3 and segments[1] == "j" else None
        return URLMetadata(platform="workable", org=segments[0] if segments else None, job_id=job_id)
    if host == "jobs.workable.com" and len(segments) >= 2 and segments[0] == "view":
        return URLMetadata(platform="workable", job_id=segments[1])
    if host == "ats.rippling.com" and len(segments) >= 3:
        return URLMetadata(platform="rippling", org=segments[0], job_id=segments[-1])
    if host.endswith(".myworkdayjobs.com"):
        tenant = host.split(".")[0]
        extra: dict[str, Any] = {}
        job_path: str | None = None
        site: str | None = None
        if "job" in segments:
            job_index = segments.index("job")
            if job_index >= 1:
                site = segments[job_index - 1]
            if len(segments) > job_index + 1:
                job_path = "/".join(segments[job_index + 1 :])
        if site:
            extra["site"] = site
        if job_path:
            extra["job_path"] = job_path
        return URLMetadata(platform="workday", org=tenant, job_id=job_path, extra=extra)
    if host.endswith(".bamboohr.com") and "careers" in segments:
        company = host.split(".")[0]
        careers_index = segments.index("careers")
        job_id = segments[careers_index + 1] if len(segments) > careers_index + 1 else None
        return URLMetadata(platform="bamboohr", org=company, job_id=job_id)
    if "brassring.com" in host:
        job_id = query.get("jobid", [None])[0] or query.get("JobId", [None])[0]
        if not job_id and parsed.fragment:
            fragment_match = re.search(r"jobDetails=(\d+)", parsed.fragment, re.IGNORECASE)
            if fragment_match:
                job_id = fragment_match.group(1)
        extra: dict[str, Any] = {}
        partner_id = query.get("partnerid", [None])[0]
        site_id = query.get("siteid", [None])[0]
        if partner_id:
            extra["partner_id"] = partner_id
        if site_id:
            extra["site_id"] = site_id
        return URLMetadata(platform="brassring", job_id=job_id, extra=extra)
    if query.get("gnk") == ["job"]:
        return URLMetadata(platform="paycor", job_id=query.get("gni", [None])[0])
    if "successfactors" in host or "successfactors" in parsed.path.lower():
        extra: dict[str, Any] = {}
        if segments and segments[0] == "job":
            if len(segments) > 1:
                extra["slug"] = segments[1]
            if len(segments) > 2:
                return URLMetadata(platform="successfactors", job_id=segments[2], extra=extra)
        return URLMetadata(platform="successfactors", extra=extra)
    if host == "workforcenow.adp.com":
        extra: dict[str, Any] = {}
        cid = query.get("cid", [None])[0]
        cc_id = query.get("ccId", [None])[0]
        if cid:
            extra["cid"] = cid
        if cc_id:
            extra["cc_id"] = cc_id
        return URLMetadata(
            platform="adp",
            org=cid,
            job_id=query.get("jobId", [None])[0],
            extra=extra,
        )
    if host == "jobs.gem.com":
        board = segments[0] if segments else None
        job_id = segments[1] if len(segments) > 1 else None
        return URLMetadata(platform="gem", org=board, job_id=job_id)
    if host.endswith(".icims.com"):
        job_id = None
        if "jobs" in segments:
            jobs_index = segments.index("jobs")
            if len(segments) > jobs_index + 1:
                job_id = segments[jobs_index + 1]
        return URLMetadata(platform="icims", job_id=job_id)
    if host.endswith(".avature.net"):
        extra: dict[str, Any] = {}
        if segments:
            extra["portal"] = segments[0]
            if "JobDetail" in segments:
                detail_index = segments.index("JobDetail")
                if len(segments) > detail_index + 2:
                    return URLMetadata(platform="avature", job_id=segments[detail_index + 2], extra=extra)
        return URLMetadata(platform="avature", extra=extra)
    if host.endswith(".oraclecloud.com") and "/hcmUI/" in parsed.path:
        extra: dict[str, Any] = {}
        site = None
        req_id = None
        if "sites" in segments:
            sites_index = segments.index("sites")
            if len(segments) > sites_index + 1:
                site = segments[sites_index + 1]
        if "job" in segments:
            job_index = segments.index("job")
            if len(segments) > job_index + 1:
                req_id = segments[job_index + 1]
        if "requisitions" in segments:
            req_index = segments.index("requisitions")
            if req_id is None and len(segments) > req_index + 1:
                req_id = segments[req_index + 1]
        if site:
            extra["site"] = site
        return URLMetadata(platform="oracle_hcm", org=host.split(".")[0], job_id=req_id, extra=extra)
    if "jobvite.com" in host:
        job_id = query.get("j", [None])[0]
        extra: dict[str, Any] = {}
        org = None
        if len(segments) >= 3 and segments[1] == "job":
            org = segments[0]
            job_id = job_id or segments[2]
        company_eid = query.get("c", [None])[0]
        if company_eid:
            extra["company_eid"] = company_eid
        return URLMetadata(platform="jobvite", org=org, job_id=job_id, extra=extra)
    return URLMetadata(platform="unknown")


def get_platform_capability(platform: str) -> dict[str, Any]:
    capability = PLATFORM_CAPABILITIES.get(platform)
    if capability is None:
        return {
            "platform": platform,
            "display_name": platform.replace("_", " ").title(),
            "supported": True,
            "integration": "generic",
            "detection": [],
            "notes": "No platform-specific wiring; generic extraction, render, sitemap, and archive fallbacks still run.",
        }

    return {
        "platform": platform,
        "display_name": capability["display_name"],
        "supported": capability["supported"],
        "integration": capability["integration"],
        "detection": list(capability["detection"]),
        "notes": capability["notes"],
    }


def list_platform_capabilities() -> list[dict[str, Any]]:
    return [get_platform_capability(platform) for platform in PLATFORM_CAPABILITIES]


def summarize_platform_capabilities() -> dict[str, int]:
    summary = {
        "supported": 0,
        "direct": 0,
        "generic": 0,
        "blocked": 0,
        "unsupported": 0,
    }
    for item in list_platform_capabilities():
        if item["supported"]:
            summary["supported"] += 1
        integration = item["integration"]
        if integration in summary:
            summary[integration] += 1
    return summary


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

    if not isinstance(value, str):
        return None

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

    for fmt in ("%B %d, %Y", "%b %d, %Y", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(cleaned, fmt).date().isoformat()
        except ValueError:
            continue

    for fmt in ("%a %b %d %H:%M:%S %Z %Y", "%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"):
        try:
            return datetime.strptime(cleaned, fmt).date().isoformat()
        except ValueError:
            continue

    try:
        return email.utils.parsedate_to_datetime(cleaned).date().isoformat()
    except (TypeError, ValueError, IndexError, OverflowError):
        pass

    try:
        return date.fromisoformat(cleaned[:10]).isoformat()
    except ValueError:
        return None


def age_days(estimated_posted: str | None, today: date | None = None) -> int | None:
    if estimated_posted is None:
        return None
    reference_day = today or utc_today()
    return (reference_day - date.fromisoformat(estimated_posted)).days


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


def extract_script_json_by_id(html: str, script_id: str) -> Any | None:
    for match in SCRIPT_JSON_BY_ID_RE.finditer(html):
        if match.group("id").lower() != script_id.lower():
            continue
        return parse_jsonish(unescape(match.group("body").strip()))
    return None


def extract_meta_tags(html: str) -> dict[str, str]:
    tags: dict[str, str] = {}
    for raw_meta in META_TAG_RE.findall(html):
        attrs = {
            key.lower(): unescape(value)
            for key, value in HTML_ATTR_RE.findall(raw_meta)
        }
        key = attrs.get("property") or attrs.get("name")
        content = attrs.get("content")
        if key and content is not None:
            tags[key.lower()] = content
    return tags


def extract_base_href(html: str) -> str | None:
    match = BASE_HREF_RE.search(html)
    if not match:
        return None
    return unescape(match.group(1)).strip()


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


def pick_first_text(value: Any, keys: set[str]) -> str | None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key.lower() in keys and isinstance(nested, str) and nested.strip():
                return nested.strip()
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def extract_location_text(job_location: Any) -> str | None:
    if isinstance(job_location, list):
        for item in job_location:
            location = extract_location_text(item)
            if location:
                return location
        return None
    if not isinstance(job_location, dict):
        return None
    address = job_location.get("address", {})
    if isinstance(address, str):
        return address.strip() or None
    if isinstance(address, dict):
        parts = [
            address.get("streetAddress"),
            address.get("addressLocality"),
            address.get("addressRegion"),
            address.get("postalCode"),
            address.get("addressCountry"),
        ]
        rendered = ", ".join(str(part).strip() for part in parts if part)
        return rendered or None
    return None


def extract_base_salary(job_posting: dict[str, Any]) -> str | None:
    salary = job_posting.get("baseSalary")
    if not isinstance(salary, dict):
        return None
    currency = salary.get("currency")
    value = salary.get("value")
    if isinstance(value, dict):
        minimum = value.get("minValue")
        maximum = value.get("maxValue")
        unit_text = value.get("unitText")
        if minimum or maximum:
            return f"{currency or ''} {minimum or '?'} - {maximum or '?'} {unit_text or ''}".strip()
    if isinstance(value, (int, float, str)):
        return f"{currency or ''} {value}".strip()
    return None


def extract_jsonld(accumulator: AnalysisAccumulator, html: str) -> None:
    for posting in extract_job_postings_from_html(html):
        accumulator.add_date(
            posting.get("datePosted"),
            source="jsonld.jobposting",
            field="datePosted",
            kind="posted",
            reliability="high",
        )
        accumulator.add_date(
            posting.get("validThrough"),
            source="jsonld.jobposting",
            field="validThrough",
            kind="expiry",
            reliability="medium",
        )
        accumulator.set_if_missing("title", posting.get("title"))

        hiring_org = posting.get("hiringOrganization")
        if isinstance(hiring_org, dict):
            accumulator.set_if_missing("company", hiring_org.get("name"))
        accumulator.set_if_missing("location", extract_location_text(posting.get("jobLocation")))
        accumulator.set_if_missing("employment_type", posting.get("employmentType"))

        identifier = posting.get("identifier")
        if isinstance(identifier, dict):
            if identifier.get("name"):
                accumulator.add_hidden("identifier_name", identifier.get("name"))
            if identifier.get("value"):
                accumulator.add_hidden("identifier_value", identifier.get("value"))

        salary = extract_base_salary(posting)
        if salary:
            accumulator.add_hidden("salary_range", salary)

        direct_apply = posting.get("directApply")
        if direct_apply is not None:
            accumulator.add_hidden("direct_apply", direct_apply)


def extract_meta_and_open_graph(accumulator: AnalysisAccumulator, html: str) -> None:
    meta = extract_meta_tags(html)
    accumulator.set_if_missing("title", meta.get("og:title") or meta.get("title"))
    accumulator.set_if_missing("company", meta.get("og:site_name"))
    accumulator.set_if_missing("location", meta.get("job:location"))

    for key in ("article:published_time", "og:published_time"):
        if key in meta:
            accumulator.add_date(
                meta[key],
                source="open_graph",
                field=key,
                kind="published",
                reliability="medium",
            )

    for key, value in meta.items():
        if "updated" in key:
            accumulator.add_date(
                value,
                source="meta",
                field=key,
                kind="refresh",
                reliability="low",
            )
        elif "lastmod" in key:
            accumulator.add_date(
                value,
                source="meta",
                field=key,
                kind="crawl",
                reliability="low",
            )


def extract_regex_dates(accumulator: AnalysisAccumulator, html: str) -> None:
    for field_name, pattern, kind, reliability in COMMON_DATE_PATTERNS:
        for match in pattern.finditer(html):
            accumulator.add_date(
                match.group(1),
                source="html.regex",
                field=field_name,
                kind=kind,
                reliability=reliability,
            )

    for match in VISIBLE_DATE_RE.finditer(unescape(html)):
        accumulator.add_date(
            match.group(1),
            source="html.visible",
            field="visible_date",
            kind="published",
            reliability="medium",
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

    if "absolute_url" in node and ("published_at" in node or "updated_at" in node or "id" in node):
        jobs.append(node)

    for value in node.values():
        jobs.extend(iter_greenhouse_jobs(value))

    return jobs


def normalized_url_path(url: str) -> str:
    parsed = urlparse(url)
    return parsed.path.rstrip("/")


def add_scalar_metadata(accumulator: AnalysisAccumulator, key: str, value: Any) -> None:
    normalized_key = key.replace("-", "").replace(":", "").replace(".", "").replace(" ", "").lower()

    if normalized_key in DATE_KEY_RULES:
        kind, reliability = DATE_KEY_RULES[normalized_key]
        accumulator.add_date(
            value,
            source="embedded.json",
            field=key,
            kind=kind,
            reliability=reliability,
        )

    if normalized_key in TEXT_TITLE_FIELDS and isinstance(value, str):
        accumulator.set_if_missing("title", value)
    elif normalized_key in TEXT_COMPANY_FIELDS:
        if isinstance(value, dict):
            accumulator.set_if_missing("company", value.get("name"))
        elif isinstance(value, str):
            accumulator.set_if_missing("company", value)
    elif normalized_key in TEXT_LOCATION_FIELDS and isinstance(value, str):
        accumulator.set_if_missing("location", value)
    elif normalized_key in TEXT_EMPLOYMENT_FIELDS and isinstance(value, str):
        accumulator.set_if_missing("employment_type", value)

    if normalized_key in HIDDEN_INSIGHT_FIELDS:
        if isinstance(value, dict):
            rendered = value.get("name") or value.get("label") or value.get("value")
            accumulator.add_hidden(normalized_key, rendered if rendered is not None else value)
        else:
            accumulator.add_hidden(normalized_key, value)


def walk_json_payload(accumulator: AnalysisAccumulator, payload: Any, path: str = "") -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            next_path = f"{path}.{key}" if path else key
            add_scalar_metadata(accumulator, key, value)
            walk_json_payload(accumulator, value, next_path)
        return

    if isinstance(payload, list):
        for item in payload:
            walk_json_payload(accumulator, item, path)


def extract_embedded_json(accumulator: AnalysisAccumulator, html: str) -> None:
    for marker in ("window.__remixContext", "window.careers", "window.workday"):
        raw_object = extract_json_object_after_marker(html, marker)
        if raw_object is None:
            continue
        parsed = parse_jsonish(raw_object)
        if parsed is not None:
            walk_json_payload(accumulator, parsed)


def detect_from_greenhouse_html(
    accumulator: AnalysisAccumulator,
    html: str,
    original_url: str,
    metadata: URLMetadata,
) -> None:
    remix_context = extract_remix_context(html)
    if remix_context is None:
        return

    target_path = normalized_url_path(original_url)
    for job in iter_greenhouse_jobs(remix_context):
        absolute_url = job.get("absolute_url") or ""
        job_id = str(job.get("id")) if job.get("id") is not None else None
        url_matches = absolute_url and normalized_url_path(absolute_url) == target_path
        id_matches = metadata.job_id is not None and metadata.job_id == job_id
        if not (url_matches or id_matches):
            continue

        accumulator.set_if_missing("title", job.get("title"))
        accumulator.set_if_missing("company", job.get("company_name"))
        accumulator.set_if_missing("location", job.get("location", {}).get("name") if isinstance(job.get("location"), dict) else job.get("location"))
        accumulator.add_date(
            job.get("published_at"),
            source="greenhouse.html",
            field="published_at",
            kind="posted",
            reliability="high",
        )
        accumulator.add_date(
            job.get("updated_at"),
            source="greenhouse.html",
            field="updated_at",
            kind="refresh",
            reliability="medium",
            note="Greenhouse updated_at reflects edits or freshness, not original posting time.",
        )


def extract_greenhouse_api(accumulator: AnalysisAccumulator, session: Any, metadata: URLMetadata) -> None:
    if not metadata.org or not metadata.job_id:
        return
    api_url = f"https://boards-api.greenhouse.io/v1/boards/{metadata.org}/jobs/{metadata.job_id}"
    try:
        payload = fetch_json(session, api_url)
    except HTTPRequestError as exc:
        accumulator.add_warning(f"Greenhouse API fallback failed: {exc}")
        return

    accumulator.set_preferred("title", payload.get("title"))
    if isinstance(payload.get("location"), dict):
        accumulator.set_preferred("location", payload["location"].get("name"))
    accumulator.add_date(
        payload.get("first_published"),
        source="greenhouse.api",
        field="first_published",
        kind="posted",
        reliability="high",
    )
    accumulator.add_date(
        payload.get("updated_at"),
        source="greenhouse.api",
        field="updated_at",
        kind="refresh",
        reliability="medium",
        note="Greenhouse updated_at reflects edits or freshness, not original posting time.",
    )


def extract_lever_api(accumulator: AnalysisAccumulator, session: Any, metadata: URLMetadata) -> None:
    if not metadata.org or not metadata.job_id:
        return
    api_url = f"https://api.lever.co/v0/postings/{metadata.org}/{metadata.job_id}?mode=json"
    try:
        payload = fetch_json(session, api_url)
    except HTTPRequestError as exc:
        accumulator.add_warning(f"Lever API fallback failed: {exc}")
        return

    accumulator.set_preferred("title", payload.get("text"))
    categories = payload.get("categories") or {}
    if isinstance(categories, dict):
        accumulator.set_preferred("location", categories.get("location"))
        accumulator.set_preferred("employment_type", categories.get("commitment"))
        accumulator.add_hidden("team", categories.get("team"))
        accumulator.add_hidden("department", categories.get("department"))
    accumulator.add_hidden("lever_hosted_url", payload.get("hostedUrl"))
    accumulator.add_date(
        payload.get("createdAt"),
        source="lever.api",
        field="createdAt",
        kind="posted",
        reliability="high",
    )


def extract_ashby_api(accumulator: AnalysisAccumulator, session: Any, metadata: URLMetadata, original_url: str) -> None:
    if not metadata.org or not metadata.job_id:
        return
    api_url = f"https://api.ashbyhq.com/posting-api/job-board/{metadata.org}"
    try:
        payload = fetch_json(session, api_url)
    except HTTPRequestError as exc:
        accumulator.add_warning(f"Ashby API fallback failed: {exc}")
        return

    jobs = payload.get("jobs", [])
    target_path = normalized_url_path(original_url)
    for job in jobs:
        job_url = (job.get("jobUrl") or "").strip()
        job_id_matches = job.get("id") == metadata.job_id
        path_matches = job_url and normalized_url_path(job_url) == target_path
        if not (job_id_matches or path_matches):
            continue

        accumulator.set_preferred("title", job.get("title"))
        accumulator.set_preferred("location", job.get("location"))
        accumulator.set_preferred("employment_type", job.get("employmentType"))
        accumulator.add_hidden("department", job.get("department"))
        accumulator.add_hidden("salary_range", job.get("salary"))
        accumulator.add_date(
            job.get("publishedAt") or job.get("publishedDate"),
            source="ashby.api",
            field="publishedAt",
            kind="posted",
            reliability="high",
        )
        return


def extract_smartrecruiters_api(accumulator: AnalysisAccumulator, session: Any, metadata: URLMetadata) -> None:
    if not metadata.org or not metadata.job_id:
        return
    api_url = f"https://api.smartrecruiters.com/v1/companies/{metadata.org}/postings/{metadata.job_id}"
    try:
        payload = fetch_json(session, api_url)
    except HTTPRequestError as exc:
        accumulator.add_warning(f"SmartRecruiters API fallback failed: {exc}")
        return

    accumulator.set_preferred("title", payload.get("name"))
    if isinstance(payload.get("company"), dict):
        accumulator.set_preferred("company", payload["company"].get("name"))
    if isinstance(payload.get("location"), dict):
        accumulator.set_preferred("location", payload["location"].get("fullLocation") or payload["location"].get("city"))
    if isinstance(payload.get("typeOfEmployment"), dict):
        accumulator.set_preferred("employment_type", payload["typeOfEmployment"].get("label"))
    if isinstance(payload.get("department"), dict):
        accumulator.add_hidden("department", payload["department"].get("label"))
    if isinstance(payload.get("customField"), list):
        for item in payload["customField"]:
            if isinstance(item, dict):
                label = item.get("fieldLabel")
                value = item.get("valueLabel")
                if label and value:
                    accumulator.add_hidden(label.lower().replace(" ", "_"), value)
    accumulator.add_date(
        payload.get("releasedDate"),
        source="smartrecruiters.api",
        field="releasedDate",
        kind="posted",
        reliability="high",
    )


def extract_rippling_embedded(accumulator: AnalysisAccumulator, html: str) -> None:
    next_data = extract_script_json_by_id(html, "__NEXT_DATA__")
    if not isinstance(next_data, dict):
        return

    job_post = next_data.get("props", {}).get("pageProps", {}).get("apiData", {}).get("jobPost")
    if not isinstance(job_post, dict):
        return

    accumulator.set_preferred("title", job_post.get("name"))
    accumulator.set_preferred("company", job_post.get("companyName"))

    work_locations = job_post.get("workLocations")
    if isinstance(work_locations, list) and work_locations:
        accumulator.set_preferred("location", work_locations[0])
    elif isinstance(work_locations, str):
        accumulator.set_preferred("location", work_locations)

    employment_type = job_post.get("employmentType")
    if isinstance(employment_type, dict):
        accumulator.set_preferred("employment_type", employment_type.get("id") or employment_type.get("label"))
    else:
        accumulator.set_preferred("employment_type", employment_type)

    if isinstance(job_post.get("department"), dict):
        accumulator.add_hidden("department", job_post["department"].get("name"))
    accumulator.add_hidden("pay_range_details", job_post.get("payRangeDetails"))
    accumulator.add_hidden("ai_evaluations_enabled", job_post.get("hasAIEvaluationsEnabled"))

    accumulator.add_date(
        job_post.get("createdOn"),
        source="rippling.embedded",
        field="createdOn",
        kind="posted",
        reliability="high",
    )


def iter_workable_job_nodes(node: Any) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []

    if isinstance(node, list):
        for item in node:
            jobs.extend(iter_workable_job_nodes(item))
        return jobs

    if not isinstance(node, dict):
        return jobs

    if any(key in node for key in ("created", "createdAt", "published_on", "publishedOn")) and (
        node.get("title") or node.get("name") or node.get("shortcode")
    ):
        jobs.append(node)

    for value in node.values():
        jobs.extend(iter_workable_job_nodes(value))

    return jobs


def select_workable_job(jobs: list[dict[str, Any]], metadata: URLMetadata) -> dict[str, Any] | None:
    if not jobs:
        return None
    if metadata.job_id:
        for job in jobs:
            candidates = {
                str(job.get("shortcode")) if job.get("shortcode") else None,
                str(job.get("id")) if job.get("id") is not None else None,
                str(job.get("code")) if job.get("code") else None,
                str(job.get("slug")) if job.get("slug") else None,
            }
            if metadata.job_id in candidates:
                return job
    return jobs[0]


def extract_workable_embedded(
    accumulator: AnalysisAccumulator,
    html: str,
    metadata: URLMetadata,
) -> None:
    raw_object = extract_json_object_after_marker(html, "window.jobBoard")
    if raw_object is None:
        raw_object = extract_json_object_after_marker(html, "__INITIAL_STATE__")
    if raw_object is None:
        return

    parsed = parse_jsonish(raw_object)
    if parsed is None:
        return

    initial_state = parsed.get("initialState") if isinstance(parsed, dict) else None
    search_root: Any = initial_state if initial_state is not None else parsed

    job = select_workable_job(iter_workable_job_nodes(search_root), metadata)
    if not isinstance(job, dict):
        return

    accumulator.set_preferred("title", job.get("title") or job.get("name"))

    company = job.get("company")
    if isinstance(company, dict):
        accumulator.set_preferred("company", company.get("name") or company.get("title"))
    elif isinstance(company, str):
        accumulator.set_preferred("company", company)
    else:
        account = job.get("account")
        account_name = account.get("name") if isinstance(account, dict) else None
        accumulator.set_preferred("company", job.get("companyName") or account_name)

    location_value = job.get("location")
    if isinstance(location_value, dict):
        parts = [location_value.get(key) for key in ("city", "region", "country")]
        rendered = ", ".join(str(part).strip() for part in parts if part)
        if rendered:
            accumulator.set_preferred("location", rendered)
        else:
            accumulator.set_preferred("location", location_value.get("fullLocation") or location_value.get("name"))
    elif isinstance(location_value, str):
        accumulator.set_preferred("location", location_value)
    elif isinstance(job.get("locations"), list) and job["locations"]:
        first = job["locations"][0]
        if isinstance(first, dict):
            parts = [first.get(key) for key in ("city", "region", "country")]
            rendered = ", ".join(str(part).strip() for part in parts if part)
            if rendered:
                accumulator.set_preferred("location", rendered)

    employment_type = job.get("employmentType") or job.get("employment_type") or job.get("type")
    if isinstance(employment_type, dict):
        accumulator.set_preferred("employment_type", employment_type.get("label") or employment_type.get("name"))
    elif isinstance(employment_type, str):
        accumulator.set_preferred("employment_type", employment_type)

    department = job.get("department")
    if isinstance(department, dict):
        accumulator.add_hidden("department", department.get("name") or department.get("label"))
    elif isinstance(department, str):
        accumulator.add_hidden("department", department)

    function = job.get("function")
    if isinstance(function, dict):
        accumulator.add_hidden("function", function.get("name") or function.get("label"))
    elif isinstance(function, str):
        accumulator.add_hidden("function", function)

    workplace = job.get("workplace") or job.get("workplaceType") or job.get("remote")
    if isinstance(workplace, str):
        accumulator.add_hidden("workplace", workplace)
    elif isinstance(workplace, bool):
        accumulator.add_hidden("workplace", "remote" if workplace else "onsite")

    shortcode = job.get("shortcode") or job.get("code")
    if shortcode:
        accumulator.add_hidden("shortcode", shortcode)

    for key in ("application_url", "applicationUrl", "url"):
        value = job.get(key)
        if isinstance(value, str) and value:
            accumulator.add_hidden("workable_url", value)
            break

    posted_value = job.get("created") or job.get("createdAt") or job.get("published_on") or job.get("publishedOn")
    accumulator.add_date(
        posted_value,
        source="workable.embedded",
        field="created",
        kind="posted",
        reliability="high",
    )

    updated_value = job.get("updated") or job.get("updatedAt") or job.get("updated_on") or job.get("updatedOn")
    accumulator.add_date(
        updated_value,
        source="workable.embedded",
        field="updated",
        kind="refresh",
        reliability="medium",
        note="Workable updated reflects edits or freshness, not original posting time.",
    )


def iter_icims_api_candidates(html: str, original_url: str) -> list[str]:
    api_roots: list[str] = []
    base_href = extract_base_href(html)
    if base_href:
        parsed_base = urlparse(base_href)
        if parsed_base.scheme and parsed_base.netloc:
            api_roots.append(f"{parsed_base.scheme}://{parsed_base.netloc}")

    parsed_original = urlparse(original_url)
    if parsed_original.netloc == "careers.icims.com":
        api_roots.append(f"{parsed_original.scheme}://{parsed_original.netloc}")

    ordered: list[str] = []
    for root in api_roots:
        if root not in ordered:
            ordered.append(root)
    return ordered


def extract_icims_api(
    accumulator: AnalysisAccumulator,
    session: Any,
    metadata: URLMetadata,
    html: str,
    original_url: str,
) -> None:
    if not metadata.job_id:
        return

    api_roots = iter_icims_api_candidates(html, original_url)
    if not api_roots:
        return

    original_path = normalized_url_path(original_url)
    for api_root in api_roots:
        for page_number in range(1, 6):
            api_url = f"{api_root}/api/jobs?limit=100&page={page_number}"
            try:
                payload = fetch_json(session, api_url)
            except HTTPRequestError as exc:
                accumulator.add_warning(f"iCIMS API fallback failed: {exc}")
                break

            jobs = payload.get("jobs")
            if not isinstance(jobs, list) or not jobs:
                break

            matched = False
            for item in jobs:
                data = item.get("data") if isinstance(item, dict) else None
                if not isinstance(data, dict):
                    continue

                apply_url = data.get("apply_url") or ""
                req_id = str(data.get("req_id")) if data.get("req_id") is not None else None
                slug = str(data.get("slug")) if data.get("slug") is not None else None
                matches = metadata.job_id in {req_id, slug}
                if not matches and apply_url:
                    matches = normalized_url_path(apply_url) == original_path
                if not matches:
                    continue

                accumulator.set_preferred("title", data.get("title"))
                accumulator.set_preferred("company", data.get("hiring_organization"))
                accumulator.set_preferred("location", data.get("full_location") or data.get("location_name"))
                accumulator.set_preferred("employment_type", data.get("employment_type"))
                accumulator.add_hidden("category", data.get("category"))
                accumulator.add_hidden("location_type", data.get("location_type"))
                accumulator.add_hidden("ats_code", data.get("ats_code"))
                accumulator.add_hidden("tags1", data.get("tags1"))
                accumulator.add_hidden("tags2", data.get("tags2"))
                accumulator.add_date(
                    data.get("posted_date"),
                    source="icims.api",
                    field="posted_date",
                    kind="posted",
                    reliability="high",
                )
                accumulator.add_date(
                    data.get("update_date"),
                    source="icims.api",
                    field="update_date",
                    kind="refresh",
                    reliability="medium",
                    note="iCIMS update_date reflects freshness, not original posting time.",
                )
                matched = True
                break

            if matched:
                return
            if len(jobs) < 100:
                break


def extract_dover_api(accumulator: AnalysisAccumulator, session: Any, metadata: URLMetadata) -> None:
    if not metadata.job_id:
        return

    api_url = f"https://app.dover.com/api/v1/inbound/application-portal-job/{metadata.job_id}"
    try:
        payload = fetch_json(session, api_url)
    except HTTPRequestError as exc:
        accumulator.add_warning(f"Dover API fallback failed: {exc}")
        return

    accumulator.set_preferred("title", payload.get("title"))
    accumulator.set_preferred("company", payload.get("client_name"))

    locations = payload.get("locations")
    if isinstance(locations, list) and locations:
        location_names = [item.get("name") for item in locations if isinstance(item, dict) and item.get("name")]
        if location_names:
            accumulator.set_preferred("location", " / ".join(location_names[:4]))
        location_types = sorted(
            {
                str(item.get("location_type")).lower()
                for item in locations
                if isinstance(item, dict) and item.get("location_type")
            }
        )
        if location_types:
            accumulator.add_hidden("workplace_types", location_types)
    elif payload.get("location"):
        accumulator.set_preferred("location", payload.get("location"))

    if isinstance(payload.get("compensation"), dict):
        compensation = payload["compensation"]
        accumulator.set_preferred("employment_type", compensation.get("employment_type"))
        accumulator.add_hidden("compensation", compensation)
    accumulator.add_hidden("compensation_details", payload.get("compensation_details"))
    accumulator.add_hidden("visa_support", payload.get("visa_support"))
    accumulator.add_hidden("active", payload.get("active"))

    accumulator.add_date(
        payload.get("created"),
        source="dover.api",
        field="created",
        kind="posted",
        reliability="high",
    )


def extract_bamboohr_api(accumulator: AnalysisAccumulator, session: Any, metadata: URLMetadata) -> None:
    if not metadata.org or not metadata.job_id:
        return

    api_url = f"https://{metadata.org}.bamboohr.com/careers/{metadata.job_id}/detail"
    try:
        payload = fetch_json(session, api_url)
    except HTTPRequestError as exc:
        accumulator.add_warning(f"BambooHR API fallback failed: {exc}")
        return

    result = payload.get("result") if isinstance(payload, dict) else None
    job = result.get("jobOpening") if isinstance(result, dict) else None
    if not isinstance(job, dict):
        return

    accumulator.set_preferred("title", job.get("jobOpeningName"))
    accumulator.set_preferred("employment_type", job.get("employmentStatusLabel"))

    location = job.get("location")
    if isinstance(location, dict):
        parts = [location.get("city"), location.get("state"), location.get("addressCountry")]
        rendered = ", ".join(str(part).strip() for part in parts if part)
        accumulator.set_preferred("location", rendered)

    accumulator.add_hidden("department", job.get("departmentLabel"))
    accumulator.add_hidden("location_type", job.get("locationType"))
    accumulator.add_hidden("minimum_experience", job.get("minimumExperience"))
    accumulator.add_hidden("seek_promoted", job.get("seekPromoted"))
    accumulator.add_hidden("job_opening_status", job.get("jobOpeningStatus"))
    accumulator.add_hidden("compensation", job.get("compensation"))

    accumulator.add_date(
        job.get("datePosted"),
        source="bamboohr.api",
        field="datePosted",
        kind="posted",
        reliability="high",
    )


def extract_jobvite_company_eid(html: str) -> str | None:
    match = re.search(r"companyEId\s*:\s*['\"]([^'\"]+)['\"]", html)
    if match:
        return match.group(1).strip()
    return None


def extract_jobvite_company_name(html: str) -> str | None:
    meta = extract_meta_tags(html)
    for candidate in (meta.get("og:site_name"), meta.get("og:title")):
        if not candidate:
            continue
        looking_match = re.match(r"(.+?)\s+is looking for\s+", candidate, re.IGNORECASE)
        if looking_match:
            return looking_match.group(1).strip()
        if "Careers - " not in candidate and " - Careers" not in candidate:
            return candidate.strip()

    title_match = re.search(r"<title>([^<]+)</title>", html, re.IGNORECASE)
    if not title_match:
        return None
    title = unescape(title_match.group(1)).strip()
    for separator in (" Careers - ", " - Careers"):
        if separator in title:
            return title.split(separator, 1)[0].strip()
    return None


def extract_jobvite_xml(
    accumulator: AnalysisAccumulator,
    session: Any,
    metadata: URLMetadata,
    html: str,
) -> None:
    if not metadata.job_id:
        return

    company_eid = metadata.extra.get("company_eid")
    if not company_eid and html:
        company_eid = extract_jobvite_company_eid(html)
    if not company_eid:
        return

    api_url = (
        "https://jobs.jobvite.com/CompanyJobs/Xml.aspx"
        f"?c={quote(company_eid, safe='')}&j={quote(metadata.job_id, safe='')}"
    )
    try:
        xml_text = fetch_text(session, api_url)
    except HTTPRequestError as exc:
        accumulator.add_warning(f"Jobvite XML fallback failed: {exc}")
        return

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return

    accumulator.set_preferred("title", root.findtext("title"))
    accumulator.set_preferred("company", extract_jobvite_company_name(html))
    accumulator.set_preferred("location", root.findtext("location"))
    accumulator.set_preferred("employment_type", root.findtext("jobtype"))

    accumulator.add_hidden("category", root.findtext("category"))
    accumulator.add_hidden("requisition_id", root.findtext("requisitionId"))
    accumulator.add_hidden("jobvite_company_eid", company_eid)
    accumulator.add_hidden("detail_url", root.findtext("detail-url"))

    accumulator.add_date(
        root.findtext("date"),
        source="jobvite.xml",
        field="date",
        kind="posted",
        reliability="high",
    )


def looks_like_successfactors(html: str) -> bool:
    lower = html.lower()
    return (
        "j2w.init" in lower
        or "rmkcdn.successfactors.com" in lower
        or "sapsf/successfactors/ns2cloud" in lower
        or "ssocompanyid" in lower
    )


def maybe_detect_html_platform(url: str, html: str, metadata: URLMetadata) -> URLMetadata:
    if metadata.platform == "unknown" and looks_like_successfactors(html):
        parsed = urlparse(url)
        segments = [segment for segment in parsed.path.split("/") if segment]
        extra: dict[str, Any] = {}
        job_id = None
        if segments and segments[0] == "job":
            if len(segments) > 1:
                extra["slug"] = segments[1]
            if len(segments) > 2:
                job_id = segments[2]
        return URLMetadata(platform="successfactors", org=parsed.netloc.lower(), job_id=job_id, extra=extra)
    return metadata


def extract_brassring_html(
    accumulator: AnalysisAccumulator,
    html: str,
) -> None:
    meta = extract_meta_tags(html)
    dc_date_match = re.search(
        r'<meta[^>]+name=["\']DC\.Date["\'][^>]+content=["\']([^"\']+)',
        html,
        re.IGNORECASE,
    )
    if dc_date_match:
        accumulator.add_date(
            dc_date_match.group(1).strip(),
            source="brassring.html",
            field="DC.Date",
            kind="posted",
            reliability="high",
        )

    title = meta.get("og:title")
    if title:
        parts = [part.strip() for part in title.split(" - ") if part.strip()]
        if parts:
            accumulator.set_preferred("title", parts[0])
        if len(parts) >= 2:
            accumulator.set_preferred("company", parts[1])


def html_lang_to_locale(html: str) -> str | None:
    match = re.search(r"<html[^>]+lang=[\"']([A-Za-z_-]+)[\"']", html, re.IGNORECASE)
    if not match:
        return None
    return match.group(1).replace("-", "_")


def extract_successfactors_itemprop_date(accumulator: AnalysisAccumulator, html: str) -> None:
    match = re.search(
        r'<meta[^>]+itemprop=["\']datePosted["\'][^>]+content=["\']([^"\']+)',
        html,
        re.IGNORECASE,
    )
    if not match:
        return
    accumulator.add_date(
        match.group(1).strip(),
        source="successfactors.rss",
        field="itemprop:datePosted",
        kind="posted",
        reliability="high",
    )


def extract_successfactors_rss(
    accumulator: AnalysisAccumulator,
    session: Any,
    metadata: URLMetadata,
    original_url: str,
    html: str,
) -> None:
    parsed = urlparse(original_url)
    slug = metadata.extra.get("slug")
    if not slug:
        segments = [segment for segment in parsed.path.split("/") if segment]
        if segments and segments[0] == "job" and len(segments) > 1:
            slug = segments[1]

    locale = html_lang_to_locale(html) or "en_US"
    if slug:
        rss_url = f"{parsed.scheme}://{parsed.netloc}/services/rss/job/?locale={quote(locale, safe='')}&keywords={quote(slug, safe='')}"
        try:
            xml_text = fetch_text(session, rss_url)
        except HTTPRequestError as exc:
            accumulator.add_warning(f"SuccessFactors RSS fallback failed: {exc}")
        else:
            try:
                root = ET.fromstring(xml_text)
            except ET.ParseError:
                root = None
            if root is not None:
                channel = root.find("channel")
                items = channel.findall("item") if channel is not None else []
                for item in items:
                    link = item.findtext("link") or ""
                    if metadata.job_id and metadata.job_id not in link and slug not in link:
                        continue
                    accumulator.add_date(
                        item.findtext("pubDate"),
                        source="successfactors.rss",
                        field="pubDate",
                        kind="posted",
                        reliability="high",
                    )
                    accumulator.set_preferred("title", item.findtext("title"))
                    break

    extract_successfactors_itemprop_date(accumulator, html)


def extract_avature_feed_or_sitemap(
    accumulator: AnalysisAccumulator,
    session: Any,
    metadata: URLMetadata,
    original_url: str,
    html: str,
) -> None:
    parsed = urlparse(original_url)
    portal = metadata.extra.get("portal")
    if not portal:
        segments = [segment for segment in parsed.path.split("/") if segment]
        if segments:
            portal = segments[0]
    if not portal:
        portal_match = re.search(r'avature\.portal\.id[^>]*content=["\']([^"\']+)', html, re.IGNORECASE)
        if portal_match:
            portal = portal_match.group(1).strip()
    if not portal:
        return

    feed_url = f"{parsed.scheme}://{parsed.netloc}/{portal}/SearchJobs/feed/"
    try:
        xml_text = fetch_text(session, feed_url)
    except HTTPRequestError as exc:
        accumulator.add_warning(f"Avature feed fallback failed: {exc}")
    else:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            root = None
        if root is not None:
            channel = root.find("channel")
            items = channel.findall("item") if channel is not None else []
            for item in items:
                link = item.findtext("link") or ""
                if not path_matches_sitemap(original_url, link, metadata):
                    continue
                accumulator.add_date(
                    item.findtext("pubDate"),
                    source="avature.feed",
                    field="pubDate",
                    kind="posted",
                    reliability="high",
                )
                accumulator.set_preferred("title", item.findtext("title"))
                break

    sitemap_index_url = f"{parsed.scheme}://{parsed.netloc}/{portal}/sitemap_index.xml"
    try:
        xml_text = fetch_text(session, sitemap_index_url)
    except HTTPRequestError:
        return

    nested_sitemaps, _ = parse_sitemap_documents(xml_text)
    for nested in nested_sitemaps[:4]:
        try:
            nested_xml = fetch_text(session, nested)
        except HTTPRequestError:
            continue
        _, entries = parse_sitemap_documents(nested_xml)
        for loc, lastmod in entries:
            if not path_matches_sitemap(original_url, loc, metadata):
                continue
            accumulator.add_date(
                lastmod,
                source="avature.sitemap",
                field="lastmod",
                kind="crawl",
                reliability="low",
                note="Avature sitemap lastmod reflects portal freshness, not always the original posting time.",
            )
            return


def extract_amazon_jobs_api(accumulator: AnalysisAccumulator, session: Any, metadata: URLMetadata) -> None:
    if not metadata.job_id:
        return

    api_url = f"https://www.amazon.jobs/en/search.json?base_query={quote(metadata.job_id, safe='')}"
    try:
        payload = fetch_json(session, api_url)
    except HTTPRequestError as exc:
        accumulator.add_warning(f"Amazon.jobs API fallback failed: {exc}")
        return

    jobs = payload.get("jobs") if isinstance(payload, dict) else None
    if not isinstance(jobs, list) or not jobs:
        return

    job = next((item for item in jobs if str(item.get("id_icims")) == metadata.job_id), jobs[0])
    if not isinstance(job, dict):
        return

    accumulator.set_preferred("title", job.get("title"))
    accumulator.set_preferred("company", "Amazon")
    accumulator.set_preferred("location", job.get("normalized_location") or job.get("location"))
    accumulator.set_preferred("employment_type", job.get("job_schedule_type"))
    accumulator.add_hidden("job_category", job.get("job_category"))
    accumulator.add_hidden("business_category", job.get("business_category"))
    accumulator.add_hidden("job_family", job.get("job_family"))

    accumulator.add_date(
        job.get("posted_date"),
        source="amazon_jobs.api",
        field="posted_date",
        kind="posted",
        reliability="high",
    )


def extract_stripe_greenhouse(accumulator: AnalysisAccumulator, session: Any, metadata: URLMetadata) -> None:
    if not metadata.job_id:
        return

    api_url = f"https://boards-api.greenhouse.io/v1/boards/stripe/jobs/{quote(metadata.job_id, safe='')}"
    try:
        payload = fetch_json(session, api_url)
    except HTTPRequestError as exc:
        accumulator.add_warning(f"Stripe Greenhouse fallback failed: {exc}")
        return

    accumulator.set_preferred("title", payload.get("title"))
    accumulator.set_preferred("company", payload.get("company_name") or "Stripe")
    if isinstance(payload.get("location"), dict):
        accumulator.set_preferred("location", payload["location"].get("name"))
    accumulator.add_hidden("requisition_id", payload.get("requisition_id"))
    accumulator.add_hidden("internal_job_id", payload.get("internal_job_id"))
    accumulator.add_date(
        payload.get("first_published"),
        source="stripe.greenhouse",
        field="first_published",
        kind="posted",
        reliability="high",
    )
    accumulator.add_date(
        payload.get("updated_at"),
        source="stripe.greenhouse",
        field="updated_at",
        kind="refresh",
        reliability="medium",
        note="Greenhouse updated_at reflects edits or freshness, not original posting time.",
    )


def extract_goldman_sachs_oracle(
    accumulator: AnalysisAccumulator,
    session: Any,
    metadata: URLMetadata,
) -> None:
    if not metadata.job_id:
        return

    api_url = (
        "https://hdpc.fa.us2.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
        f"?onlyData=true&finder=findReqs;siteNumber=LateralHiring,keyword={quote(metadata.job_id, safe='')}&expand=requisitionList"
    )
    try:
        payload = fetch_json(session, api_url)
    except HTTPRequestError as exc:
        accumulator.add_warning(f"Goldman Sachs Oracle fallback failed: {exc}")
        return

    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list) or not items:
        return
    requisitions = items[0].get("requisitionList") if isinstance(items[0], dict) else None
    if not isinstance(requisitions, list) or not requisitions:
        return
    job = requisitions[0]
    if not isinstance(job, dict):
        return

    accumulator.set_preferred("title", job.get("Title"))
    accumulator.set_preferred("company", "Goldman Sachs")
    accumulator.set_preferred("location", job.get("PrimaryLocation"))
    accumulator.add_hidden("hot_job", job.get("HotJobFlag"))
    accumulator.add_hidden("short_description", job.get("ShortDescriptionStr"))
    accumulator.add_date(
        job.get("PostedDate"),
        source="goldman_sachs.oracle",
        field="PostedDate",
        kind="posted",
        reliability="high",
    )


def extract_bendingspoons_objectid(accumulator: AnalysisAccumulator, metadata: URLMetadata) -> None:
    if not metadata.job_id or not re.fullmatch(r"[a-f0-9]{24}", metadata.job_id, re.IGNORECASE):
        return

    timestamp = int(metadata.job_id[:8], 16)
    parsed_date = datetime.fromtimestamp(timestamp, tz=timezone.utc).date()
    if parsed_date < date(2020, 1, 1) or parsed_date > utc_today():
        return

    accumulator.set_preferred("company", "Bending Spoons")
    accumulator.add_date(
        parsed_date.isoformat(),
        source="bendingspoons.objectid",
        field="objectid_timestamp",
        kind="posted",
        reliability="high",
        note="Derived from the MongoDB ObjectID embedded in the URL.",
    )


def extract_gem_job_board_api(accumulator: AnalysisAccumulator, session: Any, metadata: URLMetadata) -> None:
    if not metadata.org:
        return

    api_url = f"https://api.gem.com/job_board/v0/{quote(metadata.org, safe='')}/job_posts/"
    try:
        payload = fetch_json(session, api_url)
    except HTTPRequestError as exc:
        accumulator.add_warning(f"Gem Job Board API fallback failed: {exc}")
        return

    if not isinstance(payload, list) or not payload:
        return

    target_url = accumulator.normalized_url.rstrip("/")

    def matches_job(job: dict[str, Any]) -> bool:
        absolute_url = str(job.get("absolute_url") or "").rstrip("/")
        if absolute_url and absolute_url == target_url:
            return True
        if metadata.job_id and absolute_url.endswith("/" + metadata.job_id):
            return True
        return False

    job = next((item for item in payload if isinstance(item, dict) and matches_job(item)), None)
    if job is None:
        job = next((item for item in payload if isinstance(item, dict)), None)
    if not isinstance(job, dict):
        return

    accumulator.set_preferred("title", job.get("title"))
    accumulator.set_if_missing("company", metadata.org.replace("-", " ").title() if metadata.org else None)
    if isinstance(job.get("location"), dict):
        accumulator.set_preferred("location", job["location"].get("name"))

    employment_type = job.get("employment_type")
    if isinstance(employment_type, str):
        accumulator.set_preferred("employment_type", employment_type.replace("_", " ").title())

    accumulator.add_hidden("internal_job_id", job.get("internal_job_id"))
    accumulator.add_hidden("requisition_id", job.get("requisition_id"))

    departments = job.get("departments")
    if isinstance(departments, list) and departments:
        first_department = departments[0]
        if isinstance(first_department, dict):
            accumulator.add_hidden("department", first_department.get("name"))

    offices = job.get("offices")
    if isinstance(offices, list) and offices:
        office_names: list[str] = []
        for office in offices:
            if not isinstance(office, dict):
                continue
            location = office.get("location")
            if isinstance(location, dict) and isinstance(location.get("name"), str):
                office_names.append(location["name"])
            elif isinstance(office.get("name"), str):
                office_names.append(office["name"])
        if office_names:
            accumulator.add_hidden("offices", office_names)

    first_published_at = job.get("first_published_at")
    accumulator.add_date(
        first_published_at,
        source="gem.api",
        field="first_published_at",
        kind="posted",
        reliability="high",
    )
    if not first_published_at:
        accumulator.add_date(
            job.get("created_at"),
            source="gem.api",
            field="created_at",
            kind="posted",
            reliability="medium",
            note="Gem created_at reflects when the posting record was created; prefer first_published_at when available.",
        )
    accumulator.add_date(
        job.get("updated_at"),
        source="gem.api",
        field="updated_at",
        kind="refresh",
        reliability="medium",
        note="Gem updated_at reflects edits or freshness, not original posting time.",
    )


def extract_workday_api(
    accumulator: AnalysisAccumulator,
    session: Any,
    metadata: URLMetadata,
    original_url: str,
) -> None:
    site = metadata.extra.get("site")
    job_path = metadata.extra.get("job_path") or metadata.job_id
    if not metadata.org or not site or not job_path:
        return

    parsed = urlparse(original_url)
    api_url = f"{parsed.scheme}://{parsed.netloc}/wday/cxs/{metadata.org}/{site}/job/{job_path}"
    try:
        payload = fetch_json(session, api_url)
    except HTTPRequestError as exc:
        accumulator.add_warning(f"Workday CXS fallback failed: {exc}")
        return

    info = payload.get("jobPostingInfo") if isinstance(payload, dict) else None
    if not isinstance(info, dict):
        return

    accumulator.set_preferred("title", info.get("title"))

    hiring_org = payload.get("hiringOrganization")
    if isinstance(hiring_org, dict):
        accumulator.set_preferred("company", hiring_org.get("name"))

    location = info.get("location")
    if isinstance(location, str):
        accumulator.set_preferred("location", location)
    requisition_location = info.get("jobRequisitionLocation")
    if isinstance(requisition_location, dict):
        accumulator.set_preferred("location", requisition_location.get("descriptor") or location)

    accumulator.set_preferred("employment_type", info.get("timeType"))

    if info.get("jobReqId"):
        accumulator.add_hidden("job_req_id", info.get("jobReqId"))
    if info.get("jobPostingSiteId"):
        accumulator.add_hidden("workday_site", info.get("jobPostingSiteId"))
    country = info.get("country")
    if isinstance(country, dict) and country.get("descriptor"):
        accumulator.add_hidden("country", country.get("descriptor"))

    accumulator.add_date(
        info.get("startDate"),
        source="workday.cxs",
        field="startDate",
        kind="posted",
        reliability="high",
    )
    end_date = info.get("endDate") or info.get("postingEndDate")
    accumulator.add_date(
        end_date,
        source="workday.cxs",
        field="endDate",
        kind="expiry",
        reliability="medium",
    )


def extract_oracle_hcm_api(
    accumulator: AnalysisAccumulator,
    session: Any,
    metadata: URLMetadata,
    original_url: str,
) -> None:
    site = metadata.extra.get("site")
    req_id = metadata.job_id
    if not site or not req_id:
        return

    parsed = urlparse(original_url)
    api_url = (
        f"{parsed.scheme}://{parsed.netloc}/hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails"
        f"?onlyData=true&expand=all&finder=ById;Id=%22{quote(req_id, safe='')}%22,siteNumber={quote(site, safe='')}"
    )
    try:
        payload = fetch_json(session, api_url)
    except HTTPRequestError as exc:
        accumulator.add_warning(f"Oracle HCM fallback failed: {exc}")
        return

    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list) or not items:
        return
    item = items[0]
    if not isinstance(item, dict):
        return

    accumulator.set_preferred("title", item.get("Title"))
    primary_location = item.get("PrimaryLocation")
    if isinstance(primary_location, str):
        accumulator.set_preferred("location", primary_location)
    accumulator.set_preferred("employment_type", item.get("JobSchedule"))

    if item.get("Category"):
        accumulator.add_hidden("category", item.get("Category"))
    if item.get("RequisitionType"):
        accumulator.add_hidden("requisition_type", item.get("RequisitionType"))
    if item.get("HotJobFlag"):
        accumulator.add_hidden("hot_job", item.get("HotJobFlag"))
    if item.get("WorkplaceType"):
        accumulator.add_hidden("workplace_type", item.get("WorkplaceType"))

    accumulator.add_date(
        item.get("ExternalPostedStartDate"),
        source="oracle_hcm.api",
        field="ExternalPostedStartDate",
        kind="posted",
        reliability="high",
    )
    accumulator.add_date(
        item.get("ExternalPostedEndDate"),
        source="oracle_hcm.api",
        field="ExternalPostedEndDate",
        kind="expiry",
        reliability="medium",
    )


def should_use_render_fallback(html: str, accumulator: AnalysisAccumulator) -> bool:
    if any(candidate.kind in {"posted", "published"} for candidate in accumulator.all_dates):
        return False
    if not html.strip():
        return True
    lower_html = html.lower()
    thin_markers = (
        "please enable js",
        "cf-challenge",
        "captcha-delivery",
        "<div id=\"app\"",
        "<div id=\"root\"",
    )
    return len(html) < 2500 or any(marker in lower_html for marker in thin_markers)


def extract_dates_from_rendered_text(accumulator: AnalysisAccumulator, rendered_text: str) -> None:
    for match in VISIBLE_DATE_RE.finditer(rendered_text):
        accumulator.add_date(
            match.group(1),
            source="jina.render",
            field="visible_date",
            kind="published",
            reliability="medium",
        )

    for field_name, pattern, kind, reliability in COMMON_DATE_PATTERNS:
        for match in pattern.finditer(rendered_text):
            accumulator.add_date(
                match.group(1),
                source="jina.render",
                field=field_name,
                kind=kind,
                reliability=reliability,
            )


def extract_jina_render(accumulator: AnalysisAccumulator, session: Any) -> None:
    try:
        rendered_text = fetch_text(session, JINA_PREFIX + build_normalized_url(accumulator.url).removeprefix("https://").removeprefix("http://"))
    except HTTPRequestError as exc:
        accumulator.add_warning(f"Jina render fallback failed: {exc}")
        return
    extract_dates_from_rendered_text(accumulator, rendered_text)


def sitemap_candidates(url: str) -> list[str]:
    parsed = urlparse(url)
    root = f"{parsed.scheme}://{parsed.netloc}"
    return [f"{root}/sitemap.xml"]


def parse_sitemap_documents(xml_text: str) -> tuple[list[str], list[tuple[str, str]]]:
    sitemap_urls: list[str] = []
    entries: list[tuple[str, str]] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return sitemap_urls, entries

    namespace = ""
    if root.tag.startswith("{"):
        namespace = root.tag.split("}", 1)[0] + "}"

    if root.tag.endswith("sitemapindex"):
        for sitemap in root.findall(f"{namespace}sitemap"):
            loc = sitemap.findtext(f"{namespace}loc")
            if loc:
                sitemap_urls.append(loc.strip())
    elif root.tag.endswith("urlset"):
        for url_node in root.findall(f"{namespace}url"):
            loc = url_node.findtext(f"{namespace}loc")
            lastmod = url_node.findtext(f"{namespace}lastmod")
            if loc and lastmod:
                entries.append((loc.strip(), lastmod.strip()))
    return sitemap_urls, entries


def path_matches_sitemap(target_url: str, candidate_url: str, metadata: URLMetadata) -> bool:
    target = build_normalized_url(target_url)
    candidate = build_normalized_url(candidate_url)
    if target == candidate:
        return True
    if metadata.job_id and metadata.job_id in candidate_url:
        return True
    return normalized_url_path(target_url) == normalized_url_path(candidate_url)


def extract_sitemap_dates(accumulator: AnalysisAccumulator, session: Any, metadata: URLMetadata) -> None:
    queue = sitemap_candidates(accumulator.url)
    visited: set[str] = set()

    while queue and len(visited) < 5:
        sitemap_url = queue.pop(0)
        if sitemap_url in visited:
            continue
        visited.add(sitemap_url)
        try:
            xml_text = fetch_text(session, sitemap_url)
        except HTTPRequestError:
            continue

        nested_sitemaps, entries = parse_sitemap_documents(xml_text)
        for nested in nested_sitemaps[:5]:
            if nested not in visited:
                queue.append(nested)

        for loc, lastmod in entries:
            if path_matches_sitemap(accumulator.url, loc, metadata):
                accumulator.add_date(
                    lastmod,
                    source="sitemap",
                    field="lastmod",
                    kind="crawl",
                    reliability="low",
                    note="Sitemap lastmod reflects URL freshness, not original posting time.",
                )
                return


def extract_wayback(accumulator: AnalysisAccumulator, session: Any) -> None:
    api_url = (
        "https://web.archive.org/cdx/search/cdx"
        f"?url={quote(accumulator.url, safe='')}"
        "&limit=1&output=json&fl=timestamp,original&filter=statuscode:200&sort=ascending"
    )
    try:
        payload = fetch_json(session, api_url)
    except HTTPRequestError as exc:
        accumulator.add_warning(f"Wayback fallback failed: {exc}")
        return

    if not isinstance(payload, list) or len(payload) < 2:
        return
    first_row = payload[1]
    if not first_row:
        return
    accumulator.add_date(
        first_row[0],
        source="wayback.cdx",
        field="first_snapshot",
        kind="archive",
        reliability="low",
        note="Wayback first snapshot is a ceiling, not the true posted date.",
    )


def choose_best_date(all_dates: list[CandidateDate]) -> CandidateDate | None:
    credible = [
        candidate
        for candidate in all_dates
        if candidate.kind in {"posted", "published"} and candidate.reliability in {"high", "medium"}
    ]
    if credible:
        return sorted(
            credible,
            key=lambda item: (
                item.date,
                RELIABILITY_PRIORITY[item.reliability],
                SOURCE_PRIORITY.get(item.source, 99),
                item.source,
                item.field,
            ),
        )[0]

    if not all_dates:
        return None

    return sorted(
        all_dates,
        key=lambda item: (
            DATE_KIND_PRIORITY[item.kind],
            item.date,
            RELIABILITY_PRIORITY[item.reliability],
            SOURCE_PRIORITY.get(item.source, 99),
            item.source,
            item.field,
        ),
    )[0]


def detect_repost(best_date: CandidateDate | None, all_dates: list[CandidateDate]) -> bool:
    if best_date is None:
        return False
    best_day = date.fromisoformat(best_date.date)
    for candidate in all_dates:
        if candidate is best_date:
            continue
        if candidate.kind not in {"posted", "published", "refresh"}:
            continue
        candidate_day = date.fromisoformat(candidate.date)
        if (candidate_day - best_day).days >= 30:
            return True
    return False


def summarize_result(best_date: CandidateDate | None, reposted_likely: bool) -> str:
    if best_date is None:
        return "No credible posting date was found."
    if best_date.kind in {"posted", "published"}:
        summary = f"Oldest credible posted date is {best_date.date} from {best_date.source}.{best_date.field}."
    elif best_date.kind == "archive":
        summary = f"Earliest archive snapshot is {best_date.date}; this is only a ceiling, not the true posting date."
    elif best_date.kind == "crawl":
        summary = f"Sitemap lastmod suggests the URL existed by {best_date.date}, but that reflects freshness rather than original posting time."
    else:
        summary = f"Best available signal is {best_date.date} from {best_date.source}.{best_date.field}."
    if reposted_likely:
        summary += " Newer visible or refresh timestamps conflict with older durable evidence, so reposting or refreshing is likely."
    return summary


def build_result(
    accumulator: AnalysisAccumulator,
    *,
    today: date | None = None,
    status_override: str | None = None,
) -> dict[str, Any]:
    sorted_dates = sorted(
        accumulator.all_dates,
        key=lambda item: (item.date, DATE_KIND_PRIORITY[item.kind], RELIABILITY_PRIORITY[item.reliability]),
    )
    best_date = choose_best_date(sorted_dates)
    reposted_likely = detect_repost(best_date, sorted_dates)
    confidence = best_date.reliability if best_date else "unknown"
    status = status_override or ("success" if best_date else "no_date")
    likely_date = best_date.date if best_date else None

    return {
        "url": accumulator.url,
        "normalized_url": accumulator.normalized_url,
        "platform": accumulator.platform,
        "status": status,
        "title": accumulator.title,
        "company": accumulator.company,
        "location": accumulator.location,
        "employment_type": accumulator.employment_type,
        "likely_posted_date": likely_date,
        "likely_age_days": age_days(likely_date, today=today),
        "confidence": confidence,
        "reposted_likely": reposted_likely,
        "summary": summarize_result(best_date, reposted_likely),
        "chosen_source": best_date.as_dict() if best_date else None,
        "all_dates": [candidate.as_dict() for candidate in sorted_dates],
        "hidden_insights": accumulator.hidden_insights,
        "warnings": accumulator.warnings,
    }


def handle_blocked_or_unsupported(url: str, metadata: URLMetadata) -> dict[str, Any] | None:
    normalized_url = build_normalized_url(url)
    accumulator = AnalysisAccumulator(url=url, normalized_url=normalized_url, platform=metadata.platform)
    if metadata.platform in BLOCKED_PLATFORM_MESSAGES:
        accumulator.add_warning(BLOCKED_PLATFORM_MESSAGES[metadata.platform])
        return build_result(accumulator, status_override="blocked")
    if metadata.platform in UNSUPPORTED_PLATFORM_MESSAGES:
        accumulator.add_warning(UNSUPPORTED_PLATFORM_MESSAGES[metadata.platform])
        return build_result(accumulator, status_override="unsupported")
    return None


def analyze_url(
    url: str,
    *,
    session: Any | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    validated_url = validate_url(url)
    active_session = session or build_session()
    metadata = detect_platform(validated_url)

    blocked_result = handle_blocked_or_unsupported(validated_url, metadata)
    if blocked_result is not None:
        return blocked_result

    accumulator = AnalysisAccumulator(
        url=validated_url,
        normalized_url=build_normalized_url(validated_url),
        platform=metadata.platform,
    )

    page_fetch_error: HTTPRequestError | None = None
    html = ""
    try:
        html = fetch_text(active_session, validated_url)
    except HTTPRequestError as exc:
        page_fetch_error = exc
        accumulator.add_warning(
            f"Primary page fetch failed: {exc}. Falling back to ATS APIs, render fallback, sitemap, and archive signals."
        )

    if html:
        metadata = maybe_detect_html_platform(validated_url, html, metadata)
        extract_jsonld(accumulator, html)
        extract_meta_and_open_graph(accumulator, html)
        extract_regex_dates(accumulator, html)
        extract_embedded_json(accumulator, html)
        accumulator.platform = metadata.platform

    if metadata.platform == "lever":
        extract_lever_api(accumulator, active_session, metadata)
    elif metadata.platform == "greenhouse":
        extract_greenhouse_api(accumulator, active_session, metadata)
        if html:
            detect_from_greenhouse_html(accumulator, html, validated_url, metadata)
    elif metadata.platform == "ashby":
        extract_ashby_api(accumulator, active_session, metadata, validated_url)
    elif metadata.platform == "smartrecruiters":
        extract_smartrecruiters_api(accumulator, active_session, metadata)
    elif metadata.platform == "rippling" and html:
        extract_rippling_embedded(accumulator, html)
    elif metadata.platform == "workable" and html:
        extract_workable_embedded(accumulator, html, metadata)
    elif metadata.platform == "icims" and html:
        extract_icims_api(accumulator, active_session, metadata, html, validated_url)
    elif metadata.platform == "dover":
        extract_dover_api(accumulator, active_session, metadata)
    elif metadata.platform == "bamboohr":
        extract_bamboohr_api(accumulator, active_session, metadata)
    elif metadata.platform == "brassring" and html:
        extract_brassring_html(accumulator, html)
    elif metadata.platform == "successfactors" and html:
        extract_successfactors_rss(accumulator, active_session, metadata, validated_url, html)
    elif metadata.platform == "gem":
        extract_gem_job_board_api(accumulator, active_session, metadata)
    elif metadata.platform == "amazon_jobs":
        extract_amazon_jobs_api(accumulator, active_session, metadata)
    elif metadata.platform == "stripe":
        extract_stripe_greenhouse(accumulator, active_session, metadata)
    elif metadata.platform == "goldman_sachs":
        extract_goldman_sachs_oracle(accumulator, active_session, metadata)
    elif metadata.platform == "bending_spoons":
        extract_bendingspoons_objectid(accumulator, metadata)
    elif metadata.platform == "workday":
        extract_workday_api(accumulator, active_session, metadata, validated_url)
    elif metadata.platform == "oracle_hcm":
        extract_oracle_hcm_api(accumulator, active_session, metadata, validated_url)
    elif metadata.platform == "jobvite" and html:
        extract_jobvite_xml(accumulator, active_session, metadata, html)
    elif metadata.platform == "avature" and html:
        extract_avature_feed_or_sitemap(accumulator, active_session, metadata, validated_url, html)

    if should_use_render_fallback(html, accumulator):
        extract_jina_render(accumulator, active_session)

    extract_sitemap_dates(accumulator, active_session, metadata)
    extract_wayback(accumulator, active_session)

    result = build_result(accumulator, today=today)
    if result["status"] == "no_date" and page_fetch_error is not None and not accumulator.all_dates:
        raise PageFetchError(f"Unable to fetch job page: {validated_url}") from page_fetch_error
    return result


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
