from __future__ import annotations

import argparse
import email.utils
import json
import re
import socket
import sys
import threading
import time
import xml.etree.ElementTree as ET
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from html import unescape
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlencode, urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


ProgressEvent = dict[str, Any]
ProgressEmitter = Callable[[ProgressEvent], None]

_progress_emitter: ContextVar[ProgressEmitter | None] = ContextVar(
    "_howoldisthisjob_progress_emitter", default=None
)
_ashby_board_cache: dict[str, tuple[float, Any]] = {}
_ashby_board_cache_lock = threading.Lock()
_ashby_board_fetch_locks: dict[str, threading.Lock] = {}


def set_progress_emitter(emitter: ProgressEmitter | None) -> Token:
    """Install a progress emitter for the current context. Returns a reset token."""
    return _progress_emitter.set(emitter)


def reset_progress_emitter(token: Token) -> None:
    _progress_emitter.reset(token)


def _emit_progress(event: ProgressEvent) -> None:
    emitter = _progress_emitter.get()
    if emitter is None:
        return
    try:
        emitter(event)
    except Exception:
        # Emitter failures must never break analysis.
        pass


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/146.0.0.0 Safari/537.36"
)
DEFAULT_TIMEOUT_SECONDS = 15
ENRICHMENT_FETCH_TIMEOUT_SECONDS = 4.0
MAX_HTTP_ATTEMPTS = 3
BACKOFF_BASE_SECONDS = 0.5
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
TOTAL_ANALYSIS_BUDGET_SECONDS = 30.0
LEVER_API_TIMEOUT_SECONDS = 3.5
GREENHOUSE_API_TIMEOUT_SECONDS = 4.0
STRIPE_GREENHOUSE_API_TIMEOUT_SECONDS = 4.0
WORKABLE_API_TIMEOUT_SECONDS = 4.0
WORKDAY_API_TIMEOUT_SECONDS = 4.0
ADP_API_TIMEOUT_SECONDS = 4.0
ASHBY_BOARD_CACHE_TTL_SECONDS = 5 * 60
MIN_BUDGET_FOR_RENDER_SECONDS = 4.0
MIN_BUDGET_FOR_SITEMAP_SECONDS = 2.5
MIN_BUDGET_FOR_WAYBACK_SECONDS = 1.5
COMPARISON_SOURCES = {"sitemap", "wayback.cdx", "avature.sitemap"}
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
    "dayforce.next": 1,
    "pageup.html": 1,
    "workable.api": 1,
    "workable.embedded": 1,
    "ukg_pro.embedded": 1,
    "bamboohr.api": 1,
    "brassring.html": 1,
    "successfactors.rss": 1,
    "rippling.embedded": 1,
    "icims.api": 1,
    "dover.api": 1,
    "workday.cxs": 1,
    "adp.api": 1,
    "oracle_hcm.api": 1,
    "jobvite.xml": 1,
    "avature.feed": 1,
    "avature.sitemap": 1,
    "gem.api": 1,
    "recruitee.api": 1,
    "breezy.embedded": 1,
    "personio.xml": 1,
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
    "teamtailor": {
        "display_name": "Teamtailor",
        "supported": True,
        "integration": "direct",
        "detection": ["*.teamtailor.com/jobs/{id}-{slug}"],
        "notes": "Public Teamtailor job pages expose `article:published_time` plus JobPosting schema on the page HTML.",
    },
    "recruitee": {
        "display_name": "Recruitee",
        "supported": True,
        "integration": "direct",
        "detection": ["*.recruitee.com/o/{slug}"],
        "notes": "Public `/api/offers/{slug}` endpoint exposes `published_at`, `created_at`, and `updated_at`.",
    },
    "personio": {
        "display_name": "Personio",
        "supported": True,
        "integration": "direct",
        "detection": ["*.jobs.personio.de/job/{id}"],
        "notes": "Public Personio pages expose JobPosting schema and the XML feed at `/xml?language=...` exposes `createdAt`.",
    },
    "breezy": {
        "display_name": "Breezy HR",
        "supported": True,
        "integration": "direct",
        "detection": ["jobs.breezy.hr/p/{friendly_id}"],
        "notes": "Public Breezy pages embed a `data-position` payload with `first_publish_date` and `last_publish_date`.",
    },
    "jazzhr": {
        "display_name": "JazzHR / applytojob",
        "supported": True,
        "integration": "direct",
        "detection": ["*.applytojob.com/apply/{jobCode}"],
        "notes": "Public JazzHR detail pages expose JobPosting JSON-LD with `datePosted`.",
    },
    "custom_backend": {
        "display_name": "Custom Employer Backend",
        "supported": True,
        "integration": "direct",
        "detection": ["employer-specific public job backends"],
        "notes": "Employer-hosted public job backends that are not general ATS products but still expose durable posting dates.",
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
        "detection": [
            "gnk=job",
            "gni query param",
            "newton.newtonsoftware.com",
            "recruitingbypaycor.com",
        ],
        "notes": "Platform detection with generic extraction, sitemap, and archive fallbacks.",
    },
    "successfactors": {
        "display_name": "SAP SuccessFactors",
        "supported": True,
        "integration": "direct",
        "detection": [
            "successfactors in host or path",
            "j2w.init",
            "rmkcdn.successfactors.com",
            "ssoCompanyId",
        ],
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
    "pageup": {
        "display_name": "PageUp",
        "supported": True,
        "integration": "direct",
        "detection": ["*.pageuppeople.com", "careers-static.pageuppeople.com", "/job/{id}"],
        "notes": "Public PageUp job pages expose labeled `Advertised` and `Applications close` timestamps in the detail HTML.",
    },
    "dayforce": {
        "display_name": "Dayforce",
        "supported": True,
        "integration": "direct",
        "detection": ["jobs.dayforcehcm.com", "/jobs/{id}"],
        "notes": "Serialized Dayforce Next.js job payload exposes `postingStartTimestampUTC`, `postingExpiryTimestampUTC`, and `lastModifiedTimestampUTC` on public job pages.",
    },
    "adp": {
        "display_name": "ADP Workforce Now",
        "supported": True,
        "integration": "direct",
        "detection": ["workforcenow.adp.com"],
        "notes": "Public ADP job-requisition endpoint exposes durable requisition metadata and posting dates.",
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
        "detection": [
            "jobs.jobvite.com",
            "CompanyJobs/Xml.aspx",
            "companyEId in page config",
        ],
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
    "taleo": {
        "display_name": "Taleo",
        "supported": True,
        "integration": "direct",
        "detection": ["*.taleo.net", "viewRequisition", "jobdetail.ftl"],
        "notes": "Public Taleo requisition pages expose JobPosting schema and visible posted-date metadata on public job details.",
    },
    "ukg_pro": {
        "display_name": "UKG Pro / UltiPro",
        "supported": True,
        "integration": "direct",
        "detection": ["*.ultipro.com", "JobBoard", "OpportunityDetail"],
        "notes": "Public UKG Pro pages embed an `opportunity` payload with `PostedDate`, `UpdatedDate`, and detailed location metadata.",
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
ASHBY_TIMEZONE_RE = re.compile(r'"timezone"\s*:\s*"([^"]+)"')
HTML_ATTR_RE = re.compile(r"([A-Za-z_:][A-Za-z0-9_:\-]*)\s*=\s*[\"'](.*?)[\"']")
VISIBLE_DATE_RE = re.compile(
    r"(?:(?:date\s+posted|posted|published|listing date|open date)\s*[:\-]?\s*)"
    r"([A-Z][a-z]{2,8}\s+\d{1,2},\s+\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})",
    re.IGNORECASE,
)
COMMON_DATE_PATTERNS = (
    (
        "datePosted",
        re.compile(r"datePosted[\"']?\s*[:=]\s*[\"']([^\"']+)[\"']", re.IGNORECASE),
        "posted",
        "high",
    ),
    (
        "first_published",
        re.compile(
            r"first_published[\"']?\s*[:=]\s*[\"']([^\"']+)[\"']", re.IGNORECASE
        ),
        "posted",
        "high",
    ),
    (
        "published_at",
        re.compile(r"published_at[\"']?\s*[:=]\s*[\"']([^\"']+)[\"']", re.IGNORECASE),
        "published",
        "medium",
    ),
    (
        "publishedAt",
        re.compile(r"publishedAt[\"']?\s*[:=]\s*[\"']([^\"']+)[\"']", re.IGNORECASE),
        "published",
        "medium",
    ),
    (
        "createdAt",
        re.compile(r"createdAt[\"']?\s*[:=]\s*[\"']([^\"']+)[\"']", re.IGNORECASE),
        "posted",
        "low",
    ),
    (
        "releasedDate",
        re.compile(r"releasedDate[\"']?\s*[:=]\s*[\"']([^\"']+)[\"']", re.IGNORECASE),
        "posted",
        "high",
    ),
    (
        "updated_at",
        re.compile(r"updated_at[\"']?\s*[:=]\s*[\"']([^\"']+)[\"']", re.IGNORECASE),
        "refresh",
        "medium",
    ),
    (
        "updatedAt",
        re.compile(r"updatedAt[\"']?\s*[:=]\s*[\"']([^\"']+)[\"']", re.IGNORECASE),
        "refresh",
        "medium",
    ),
    (
        "validThrough",
        re.compile(r"validThrough[\"']?\s*[:=]\s*[\"']([^\"']+)[\"']", re.IGNORECASE),
        "expiry",
        "medium",
    ),
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
TEXT_COMPANY_FIELDS = {
    "company",
    "companyname",
    "hiringorganization",
    "organization",
    "accountname",
}
TEXT_LOCATION_FIELDS = {"location", "fulllocation", "city", "region"}
TEXT_EMPLOYMENT_FIELDS = {
    "employmenttype",
    "typeofemployment",
    "employeetype",
    "workpersona",
}
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
    final_url: str | None = None

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
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
            "Accept-Language": "en-US,en;q=0.9",
        }
        self.opener = opener
        self.sleeper = sleeper
        self.max_attempts = max_attempts

    def _backoff_seconds(self, attempt_number: int) -> float:
        return BACKOFF_BASE_SECONDS * (2 ** (attempt_number - 1))

    def request(
        self,
        method: str,
        url: str,
        timeout: int | float,
        *,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> HTTPResponse:
        merged_headers = dict(self.headers)
        if headers:
            merged_headers.update(headers)
        request = Request(url, data=data, headers=merged_headers, method=method.upper())
        last_error: HTTPRequestError | None = None
        call_deadline = time.monotonic() + max(float(timeout), 1.0)

        for attempt_number in range(1, self.max_attempts + 1):
            remaining_seconds = max(0.0, call_deadline - time.monotonic())
            if remaining_seconds <= 0:
                raise last_error or HTTPRequestError(
                    f"The read operation timed out for url: {url}",
                    retryable=True,
                )
            try:
                with self.opener(request, timeout=remaining_seconds) as response:
                    charset = response.headers.get_content_charset() or "utf-8"
                    body = response.read().decode(charset, errors="replace")
                    status_code = getattr(response, "status", response.getcode())
                    final_url = None
                    if hasattr(response, "geturl"):
                        try:
                            final_url = response.geturl()
                        except Exception:
                            final_url = None
                    return HTTPResponse(
                        text=body, status_code=status_code, final_url=final_url
                    )
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

            sleep_seconds = min(
                self._backoff_seconds(attempt_number),
                max(0.0, call_deadline - time.monotonic()),
            )
            if sleep_seconds > 0:
                self.sleeper(sleep_seconds)

        raise last_error or HTTPRequestError(f"Unknown request failure for url: {url}")

    def get(self, url: str, timeout: int | float) -> HTTPResponse:
        return self.request("GET", url, timeout)


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
        tz_name: str | None = None,
    ) -> None:
        normalized = normalize_date(raw_value, tz_name=tz_name)
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
        if not any(
            existing.as_dict() == candidate.as_dict() for existing in self.all_dates
        ):
            self.all_dates.append(candidate)


@dataclass
class RequestBudget:
    deadline_monotonic: float

    @classmethod
    def start(cls, total_seconds: float) -> "RequestBudget":
        return cls(deadline_monotonic=time.monotonic() + max(total_seconds, 1.0))

    def remaining_seconds(self) -> float:
        return max(0.0, self.deadline_monotonic - time.monotonic())

    def exhausted(self) -> bool:
        return self.remaining_seconds() <= 0.0

    def can_run(self, minimum_seconds: float = 0.0) -> bool:
        return self.remaining_seconds() >= minimum_seconds


class BudgetedSession:
    def __init__(self, base_session: Any, budget: RequestBudget) -> None:
        self.base_session = base_session
        self.budget = budget

    def request(
        self,
        method: str,
        url: str,
        timeout: int | float,
        *,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> HTTPResponse:
        remaining = self.budget.remaining_seconds()
        if remaining <= 0:
            raise HTTPRequestError(
                f"Analysis time budget exhausted before requesting url: {url}"
            )
        effective_timeout = max(0.01, min(float(timeout), remaining))
        if hasattr(self.base_session, "request"):
            return self.base_session.request(
                method,
                url,
                timeout=effective_timeout,
                data=data,
                headers=headers,
            )
        if method.upper() != "GET" or data is not None or headers:
            raise HTTPRequestError(
                f"Session does not support {method.upper()} requests for url: {url}"
            )
        return self.base_session.get(url, timeout=effective_timeout)

    def get(self, url: str, timeout: int | float) -> HTTPResponse:
        return self.request("GET", url, timeout)


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
    if host.endswith(".teamtailor.com"):
        if "jobs" in segments:
            jobs_index = segments.index("jobs")
            return URLMetadata(
                platform="teamtailor",
                org=host.split(".")[0],
                job_id=segments[jobs_index + 1]
                if len(segments) > jobs_index + 1
                else None,
            )
        if len(segments) >= 1 and re.fullmatch(
            r"\d+(?:-[a-z0-9-]+)?", segments[-1], re.IGNORECASE
        ):
            return URLMetadata(
                platform="teamtailor",
                org=host.split(".")[0],
                job_id=segments[-1],
            )
    if host.endswith(".recruitee.com") and segments and segments[0] == "o":
        return URLMetadata(
            platform="recruitee",
            org=host.split(".")[0],
            job_id=segments[1] if len(segments) > 1 else None,
        )
    if host.endswith(".jobs.personio.de") and segments and segments[0] == "job":
        return URLMetadata(
            platform="personio",
            org=host.split(".")[0],
            job_id=segments[1] if len(segments) > 1 else None,
        )
    if (
        (host == "jobs.breezy.hr" or host.endswith(".breezy.hr"))
        and segments
        and segments[0] == "p"
    ):
        return URLMetadata(
            platform="breezy", job_id=segments[1] if len(segments) > 1 else None
        )
    if host.endswith(".applytojob.com") and segments and segments[0] == "apply":
        if len(segments) >= 3 and segments[1] == "jobs" and segments[2] == "details":
            return URLMetadata(
                platform="jazzhr",
                org=host.split(".")[0],
                job_id=segments[3] if len(segments) > 3 else None,
            )
        return URLMetadata(
            platform="jazzhr",
            org=host.split(".")[0],
            job_id=segments[1] if len(segments) > 1 else None,
        )
    if host == "www.amazon.jobs":
        extra: dict[str, Any] = {"resolver": "amazon_jobs"}
        job_match = re.search(r"/jobs/([^/?#]+)", parsed.path, re.IGNORECASE)
        job_id = job_match.group(1) if job_match else None
        if job_id:
            trailing = parsed.path.split(f"/jobs/{job_id}", 1)[-1].strip("/")
            if trailing:
                extra["job_slug"] = trailing.split("/")[-1]
        return URLMetadata(
            platform="custom_backend",
            job_id=job_id,
            extra=extra,
        )
    if host == "stripe.com" and "/jobs/listing/" in parsed.path:
        job_match = re.search(r"/jobs/listing/[^/]+/(\d+)", parsed.path, re.IGNORECASE)
        return URLMetadata(
            platform="greenhouse",
            job_id=job_match.group(1) if job_match else None,
            extra={"resolver": "stripe"},
        )
    if host == "higher.gs.com" and "/roles/" in parsed.path:
        job_match = re.search(r"/roles/(\d+)", parsed.path, re.IGNORECASE)
        return URLMetadata(
            platform="oracle_hcm",
            job_id=job_match.group(1) if job_match else None,
            extra={"resolver": "goldman_sachs"},
        )
    if host == "jobs.bendingspoons.com":
        job_match = re.search(r"/positions/([a-f0-9]{24})", parsed.path, re.IGNORECASE)
        return URLMetadata(
            platform="custom_backend",
            job_id=job_match.group(1) if job_match else None,
            extra={"resolver": "bending_spoons"},
        )
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
    if host.endswith(".pageuppeople.com") and "job" in segments:
        job_index = segments.index("job")
        return URLMetadata(
            platform="pageup",
            org=segments[0] if segments else None,
            job_id=segments[job_index + 1] if len(segments) > job_index + 1 else None,
        )
    if host == "jobs.dayforcehcm.com":
        org = segments[1] if len(segments) > 1 else None
        extra: dict[str, Any] = {}
        if segments:
            extra["locale"] = segments[0]
        if len(segments) > 2:
            extra["career_site"] = segments[2]
        if "jobs" in segments:
            jobs_index = segments.index("jobs")
            job_id = segments[jobs_index + 1] if len(segments) > jobs_index + 1 else None
            return URLMetadata(
                platform="dayforce",
                org=org,
                job_id=job_id,
                extra=extra,
            )
        return URLMetadata(platform="dayforce", org=org, extra=extra)
    if host == "apply.workable.com":
        job_id = segments[2] if len(segments) >= 3 and segments[1] == "j" else None
        return URLMetadata(
            platform="workable", org=segments[0] if segments else None, job_id=job_id
        )
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
        job_id = (
            segments[careers_index + 1] if len(segments) > careers_index + 1 else None
        )
        return URLMetadata(platform="bamboohr", org=company, job_id=job_id)
    if "brassring.com" in host:
        job_id = query.get("jobid", [None])[0] or query.get("JobId", [None])[0]
        if not job_id and parsed.fragment:
            fragment_match = re.search(
                r"jobDetails=(\d+)", parsed.fragment, re.IGNORECASE
            )
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
                return URLMetadata(
                    platform="successfactors", job_id=segments[2], extra=extra
                )
        return URLMetadata(platform="successfactors", extra=extra)
    if host == "workforcenow.adp.com":
        extra: dict[str, Any] = {}
        cid = query.get("cid", [None])[0]
        cc_id = query.get("ccId", [None])[0]
        lang = query.get("lang", [None])[0]
        if cid:
            extra["cid"] = cid
        if cc_id:
            extra["cc_id"] = cc_id
        if lang:
            extra["lang"] = lang
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
    if "taleo.net" in host:
        extra: dict[str, Any] = {}
        org = query.get("org", [None])[0]
        if org:
            extra["org_code"] = org
        cws = query.get("cws", [None])[0]
        if cws:
            extra["career_section"] = cws
        job_id = query.get("rid", [None])[0] or query.get("job", [None])[0]
        return URLMetadata(platform="taleo", org=org, job_id=job_id, extra=extra)
    if host.endswith(".ultipro.com") and "JobBoard" in segments:
        extra: dict[str, Any] = {}
        if len(segments) > 2:
            extra["job_board_id"] = segments[2]
        if len(segments) > 3:
            extra["view"] = segments[3]
        job_id = query.get("opportunityId", [None])[0]
        return URLMetadata(
            platform="ukg_pro",
            org=segments[0] if segments else None,
            job_id=job_id,
            extra=extra,
        )
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
                    return URLMetadata(
                        platform="avature",
                        job_id=segments[detail_index + 2],
                        extra=extra,
                    )
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
        return URLMetadata(
            platform="oracle_hcm", org=host.split(".")[0], job_id=req_id, extra=extra
        )
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


def extract_ashby_timezone(html: str) -> str | None:
    match = ASHBY_TIMEZONE_RE.search(html)
    if not match:
        return None
    timezone_name = match.group(1).strip()
    return timezone_name or None


def normalize_date(value: Any, *, tz_name: str | None = None) -> str | None:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 1_000_000_000_000:
            timestamp /= 1000.0
        parsed = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        if tz_name:
            try:
                parsed = parsed.astimezone(ZoneInfo(tz_name))
            except ZoneInfoNotFoundError:
                pass
        return parsed.date().isoformat()

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
        parsed = datetime.fromisoformat(cleaned)
        if tz_name and parsed.tzinfo is not None:
            try:
                parsed = parsed.astimezone(ZoneInfo(tz_name))
            except ZoneInfoNotFoundError:
                pass
        return parsed.date().isoformat()
    except ValueError:
        pass

    for fmt in (
        "%B %d, %Y",
        "%b %d, %Y",
        "%m/%d/%Y",
        "%Y/%m/%d",
        "%Y-%m-%d %H:%M:%S %Z",
    ):
        try:
            return datetime.strptime(cleaned, fmt).date().isoformat()
        except ValueError:
            continue

    for fmt in (
        "%a %b %d %H:%M:%S %Z %Y",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%a, %d %b %Y %H:%M:%S %z",
    ):
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


def fetch_text(
    session: Any, url: str, *, timeout: int | float = DEFAULT_TIMEOUT_SECONDS
) -> str:
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    return response.text


def fetch_json(
    session: Any, url: str, *, timeout: int | float = DEFAULT_TIMEOUT_SECONDS
) -> Any:
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    try:
        return response.json()
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        raw = getattr(response, "text", "").strip()
        if not raw:
            raise HTTPRequestError(f"Empty JSON payload for url: {url}") from exc
        try:
            return json.loads(raw)
        except json.JSONDecodeError as decode_exc:
            raise HTTPRequestError(
                f"Malformed JSON payload for url: {url}: {decode_exc}"
            ) from decode_exc


def _cached_ashby_board_payload(org: str) -> Any | None:
    with _ashby_board_cache_lock:
        entry = _ashby_board_cache.get(org)
        if entry is None:
            return None
        expires_at, payload = entry
        if expires_at <= time.monotonic():
            _ashby_board_cache.pop(org, None)
            return None
        return payload


def fetch_ashby_board_payload(session: Any, org: str) -> Any:
    cached = _cached_ashby_board_payload(org)
    if cached is not None:
        return cached

    with _ashby_board_cache_lock:
        board_lock = _ashby_board_fetch_locks.setdefault(org, threading.Lock())

    with board_lock:
        cached = _cached_ashby_board_payload(org)
        if cached is not None:
            return cached

        payload = fetch_json(session, f"https://api.ashbyhq.com/posting-api/job-board/{org}")
        with _ashby_board_cache_lock:
            _ashby_board_cache[org] = (
                time.monotonic() + ASHBY_BOARD_CACHE_TTL_SECONDS,
                payload,
            )
        return payload


def fetch_json_request(
    session: Any,
    method: str,
    url: str,
    *,
    payload: Any | None = None,
    headers: dict[str, str] | None = None,
    timeout: int | float = DEFAULT_TIMEOUT_SECONDS,
) -> Any:
    encoded_payload = None
    merged_headers = dict(headers or {})
    if payload is not None:
        encoded_payload = json.dumps(payload).encode("utf-8")
        merged_headers.setdefault("Content-Type", "application/json")
    merged_headers.setdefault("Accept", "application/json")

    if hasattr(session, "request"):
        response = session.request(
            method,
            url,
            timeout=timeout,
            data=encoded_payload,
            headers=merged_headers,
        )
    elif method.upper() == "GET" and payload is None and not headers:
        response = session.get(url, timeout=timeout)
    else:
        raise HTTPRequestError(
            f"Session does not support {method.upper()} requests for url: {url}"
        )

    response.raise_for_status()
    try:
        return response.json()
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        raw = getattr(response, "text", "").strip()
        if not raw:
            raise HTTPRequestError(f"Empty JSON payload for url: {url}") from exc
        try:
            return json.loads(raw)
        except json.JSONDecodeError as decode_exc:
            raise HTTPRequestError(
                f"Malformed JSON payload for url: {url}: {decode_exc}"
            ) from decode_exc


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
        accumulator.set_if_missing(
            "location", extract_location_text(posting.get("jobLocation"))
        )
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

    if "absolute_url" in node and (
        "published_at" in node or "updated_at" in node or "id" in node
    ):
        jobs.append(node)

    for value in node.values():
        jobs.extend(iter_greenhouse_jobs(value))

    return jobs


def normalized_url_path(url: str) -> str:
    parsed = urlparse(url)
    return parsed.path.rstrip("/")


def add_scalar_metadata(accumulator: AnalysisAccumulator, key: str, value: Any) -> None:
    normalized_key = (
        key.replace("-", "").replace(":", "").replace(".", "").replace(" ", "").lower()
    )

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
            accumulator.add_hidden(
                normalized_key, rendered if rendered is not None else value
            )
        else:
            accumulator.add_hidden(normalized_key, value)


def walk_json_payload(
    accumulator: AnalysisAccumulator, payload: Any, path: str = ""
) -> None:
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
        accumulator.set_if_missing(
            "location",
            job.get("location", {}).get("name")
            if isinstance(job.get("location"), dict)
            else job.get("location"),
        )
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


def extract_greenhouse_api(
    accumulator: AnalysisAccumulator, session: Any, metadata: URLMetadata
) -> None:
    if not metadata.org or not metadata.job_id:
        return
    api_url = f"https://boards-api.greenhouse.io/v1/boards/{metadata.org}/jobs/{metadata.job_id}"
    try:
        payload = fetch_json(session, api_url, timeout=GREENHOUSE_API_TIMEOUT_SECONDS)
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


def extract_lever_api(
    accumulator: AnalysisAccumulator, session: Any, metadata: URLMetadata
) -> None:
    if not metadata.org or not metadata.job_id:
        return
    api_url = (
        f"https://api.lever.co/v0/postings/{metadata.org}/{metadata.job_id}?mode=json"
    )
    try:
        payload = fetch_json(session, api_url, timeout=LEVER_API_TIMEOUT_SECONDS)
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


def extract_ashby_api(
    accumulator: AnalysisAccumulator,
    session: Any,
    metadata: URLMetadata,
    original_url: str,
    html: str = "",
) -> None:
    if not metadata.org or not metadata.job_id:
        return
    try:
        payload = fetch_ashby_board_payload(session, metadata.org)
    except HTTPRequestError as exc:
        accumulator.add_warning(f"Ashby API fallback failed: {exc}")
        return

    jobs = payload.get("jobs", [])
    target_path = normalized_url_path(original_url)
    timezone_name = extract_ashby_timezone(html) if html else None
    if timezone_name:
        accumulator.add_hidden("posting_timezone", timezone_name)
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
        published_at = job.get("publishedAt") or job.get("publishedDate")
        accumulator.add_date(
            published_at,
            source="ashby.api",
            field="publishedAt",
            kind="posted",
            reliability="high",
            note=(
                f"Normalized from {published_at} using posting timezone {timezone_name}."
                if timezone_name and isinstance(published_at, str)
                else None
            ),
            tz_name=timezone_name,
        )
        return


def extract_smartrecruiters_api(
    accumulator: AnalysisAccumulator, session: Any, metadata: URLMetadata
) -> None:
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
        accumulator.set_preferred(
            "location",
            payload["location"].get("fullLocation") or payload["location"].get("city"),
        )
    if isinstance(payload.get("typeOfEmployment"), dict):
        accumulator.set_preferred(
            "employment_type", payload["typeOfEmployment"].get("label")
        )
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

    job_post = (
        next_data.get("props", {})
        .get("pageProps", {})
        .get("apiData", {})
        .get("jobPost")
    )
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
        accumulator.set_preferred(
            "employment_type", employment_type.get("id") or employment_type.get("label")
        )
    else:
        accumulator.set_preferred("employment_type", employment_type)

    if isinstance(job_post.get("department"), dict):
        accumulator.add_hidden("department", job_post["department"].get("name"))
    accumulator.add_hidden("pay_range_details", job_post.get("payRangeDetails"))
    accumulator.add_hidden(
        "ai_evaluations_enabled", job_post.get("hasAIEvaluationsEnabled")
    )

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

    if any(
        key in node for key in ("created", "createdAt", "published_on", "publishedOn")
    ) and (node.get("title") or node.get("name") or node.get("shortcode")):
        jobs.append(node)

    for value in node.values():
        jobs.extend(iter_workable_job_nodes(value))

    return jobs


def select_workable_job(
    jobs: list[dict[str, Any]], metadata: URLMetadata
) -> dict[str, Any] | None:
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
        accumulator.set_preferred(
            "company", company.get("name") or company.get("title")
        )
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
            accumulator.set_preferred(
                "location",
                location_value.get("fullLocation") or location_value.get("name"),
            )
    elif isinstance(location_value, str):
        accumulator.set_preferred("location", location_value)
    elif isinstance(job.get("locations"), list) and job["locations"]:
        first = job["locations"][0]
        if isinstance(first, dict):
            parts = [first.get(key) for key in ("city", "region", "country")]
            rendered = ", ".join(str(part).strip() for part in parts if part)
            if rendered:
                accumulator.set_preferred("location", rendered)

    employment_type = (
        job.get("employmentType") or job.get("employment_type") or job.get("type")
    )
    if isinstance(employment_type, dict):
        accumulator.set_preferred(
            "employment_type",
            employment_type.get("label") or employment_type.get("name"),
        )
    elif isinstance(employment_type, str):
        accumulator.set_preferred("employment_type", employment_type)

    department = job.get("department")
    if isinstance(department, dict):
        accumulator.add_hidden(
            "department", department.get("name") or department.get("label")
        )
    elif isinstance(department, str):
        accumulator.add_hidden("department", department)

    function = job.get("function")
    if isinstance(function, dict):
        accumulator.add_hidden(
            "function", function.get("name") or function.get("label")
        )
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

    posted_value = (
        job.get("created")
        or job.get("createdAt")
        or job.get("published_on")
        or job.get("publishedOn")
    )
    accumulator.add_date(
        posted_value,
        source="workable.embedded",
        field="created",
        kind="posted",
        reliability="high",
    )

    updated_value = (
        job.get("updated")
        or job.get("updatedAt")
        or job.get("updated_on")
        or job.get("updatedOn")
    )
    accumulator.add_date(
        updated_value,
        source="workable.embedded",
        field="updated",
        kind="refresh",
        reliability="medium",
        note="Workable updated reflects edits or freshness, not original posting time.",
    )


def render_dayforce_company_name(site_info: dict[str, Any]) -> str | None:
    candidate_name = site_info.get("candidateCorrespondenceClientName")
    if isinstance(candidate_name, str) and candidate_name.strip():
        cleaned = re.sub(
            r"\s+recruiting team$",
            "",
            candidate_name.strip(),
            flags=re.IGNORECASE,
        ).strip()
        return cleaned or candidate_name.strip()

    client_namespace = site_info.get("clientNamespace")
    if isinstance(client_namespace, str) and client_namespace.strip():
        parts = re.split(r"[_\-]+", client_namespace.strip())
        if len(parts) > 1:
            return " ".join(part.capitalize() for part in parts if part)
        return client_namespace.strip()

    return None


def render_dayforce_location(location: dict[str, Any]) -> str | None:
    formatted = location.get("formattedAddress")
    if isinstance(formatted, str) and formatted.strip():
        return formatted.strip()

    parts = [
        location.get("cityName"),
        location.get("stateCode"),
        location.get("isoCountryCode"),
    ]
    rendered = ", ".join(str(part).strip() for part in parts if part)
    return rendered or None


def extract_dayforce_next_data(
    accumulator: AnalysisAccumulator,
    html: str,
) -> None:
    payload = extract_script_json_by_id(html, "__NEXT_DATA__")
    if not isinstance(payload, dict):
        return

    props = payload.get("props")
    if not isinstance(props, dict):
        return
    page_props = props.get("pageProps")
    if not isinstance(page_props, dict):
        return

    job_data = page_props.get("jobData")
    site_info: dict[str, Any] | None = None

    dehydrated_state = page_props.get("dehydratedState")
    queries = (
        dehydrated_state.get("queries")
        if isinstance(dehydrated_state, dict)
        else None
    )
    if isinstance(queries, list):
        for query in queries:
            if not isinstance(query, dict):
                continue
            state = query.get("state")
            data = state.get("data") if isinstance(state, dict) else None
            if not isinstance(data, dict):
                continue
            if not isinstance(job_data, dict) and "postingStartTimestampUTC" in data:
                job_data = data
            query_key = query.get("queryKey")
            if (
                site_info is None
                and isinstance(query_key, list)
                and query_key
                and query_key[0] == "site-info"
            ):
                site_info = data

    if not isinstance(job_data, dict):
        return

    accumulator.set_preferred("title", job_data.get("jobTitle"))
    if isinstance(site_info, dict):
        accumulator.set_preferred("company", render_dayforce_company_name(site_info))
    first_location = None
    posting_locations = job_data.get("postingLocations")
    if isinstance(posting_locations, list) and posting_locations:
        first_location = posting_locations[0]
    if isinstance(first_location, dict):
        accumulator.set_preferred("location", render_dayforce_location(first_location))

    attributes = job_data.get("jobPostingAttributes")
    if isinstance(attributes, list):
        for attribute in attributes:
            if not isinstance(attribute, dict):
                continue
            name = attribute.get("name")
            value = attribute.get("value")
            if name == "EmploymentIndicator":
                accumulator.set_preferred("employment_type", value)
            elif name in {"PayType", "JobFunction", "JobFamily"}:
                accumulator.add_hidden(name.lower(), value)

    if job_data.get("jobReqId") is not None:
        accumulator.add_hidden("job_req_id", job_data.get("jobReqId"))
    if job_data.get("jobPostingId") is not None:
        accumulator.add_hidden("dayforce_job_posting_id", job_data.get("jobPostingId"))
    if isinstance(first_location, dict):
        accumulator.add_hidden("iso_country_code", first_location.get("isoCountryCode"))
        accumulator.add_hidden("state_code", first_location.get("stateCode"))

    accumulator.add_date(
        job_data.get("postingStartTimestampUTC"),
        source="dayforce.next",
        field="postingStartTimestampUTC",
        kind="posted",
        reliability="high",
    )
    accumulator.add_date(
        job_data.get("lastModifiedTimestampUTC"),
        source="dayforce.next",
        field="lastModifiedTimestampUTC",
        kind="refresh",
        reliability="medium",
        note="Dayforce last-modified timestamps reflect page edits or repost freshness, not the original posting date.",
    )
    accumulator.add_date(
        job_data.get("postingExpiryTimestampUTC"),
        source="dayforce.next",
        field="postingExpiryTimestampUTC",
        kind="expiry",
        reliability="medium",
    )


def render_ukg_location(location: dict[str, Any]) -> str | None:
    localized_name = location.get("LocalizedName")
    if isinstance(localized_name, str) and localized_name.strip():
        return localized_name.strip()

    address = location.get("Address")
    if isinstance(address, dict):
        parts = [
            address.get("City"),
            address.get("State", {}).get("Code")
            if isinstance(address.get("State"), dict)
            else None,
            address.get("Country", {}).get("Name")
            if isinstance(address.get("Country"), dict)
            else None,
        ]
        rendered = ", ".join(str(part).strip() for part in parts if part)
        if rendered:
            return rendered

    return None


def extract_ukg_pro_embedded(accumulator: AnalysisAccumulator, html: str) -> None:
    raw_object = extract_json_object_after_marker(
        html, "var opportunity = new US.Opportunity.CandidateOpportunityDetail"
    )
    if raw_object is None:
        raw_object = extract_json_object_after_marker(html, "var opportunity")
    if raw_object is None:
        return

    payload = parse_jsonish(raw_object)
    if not isinstance(payload, dict):
        return

    accumulator.set_preferred("title", payload.get("Title"))
    if payload.get("FullTime") is True:
        accumulator.set_preferred("employment_type", "Full-time")
    elif payload.get("FullTime") is False:
        accumulator.set_preferred("employment_type", "Part-time")

    locations = payload.get("Locations")
    if isinstance(locations, list) and locations:
        first = locations[0]
        if isinstance(first, dict):
            accumulator.set_preferred("location", render_ukg_location(first))
            accumulator.set_preferred("company", first.get("LocalizedDescription"))
            accumulator.add_hidden("location_name", first.get("LocalizedName"))

    if payload.get("RequisitionNumber"):
        accumulator.add_hidden("requisition_number", payload.get("RequisitionNumber"))
    if payload.get("JobCategoryName"):
        accumulator.add_hidden("job_category", payload.get("JobCategoryName"))
    if payload.get("TravelRequired") is not None:
        accumulator.add_hidden("travel_required", payload.get("TravelRequired"))
    if payload.get("JobLocationType"):
        accumulator.add_hidden("job_location_type", payload.get("JobLocationType"))
    if payload.get("HoursPerWeek"):
        accumulator.add_hidden("hours_per_week", payload.get("HoursPerWeek"))

    accumulator.add_date(
        payload.get("PostedDate"),
        source="ukg_pro.embedded",
        field="PostedDate",
        kind="posted",
        reliability="high",
    )
    accumulator.add_date(
        payload.get("UpdatedDate"),
        source="ukg_pro.embedded",
        field="UpdatedDate",
        kind="refresh",
        reliability="medium",
        note="UKG updated timestamps reflect edits or refresh activity, not the original posting date.",
    )

    memberships = payload.get("JobBoardMemberships")
    if isinstance(memberships, list):
        for membership in memberships:
            if not isinstance(membership, dict):
                continue
            accumulator.add_date(
                membership.get("ExternalPostedDate") or membership.get("InternalPostedDate"),
                source="ukg_pro.embedded",
                field="JobBoardMemberships",
                kind="posted",
                reliability="high",
            )


def render_workable_location(job: dict[str, Any]) -> str | None:
    location_value = job.get("location")
    if isinstance(location_value, dict):
        parts = [location_value.get(key) for key in ("city", "region", "country")]
        rendered = ", ".join(str(part).strip() for part in parts if part)
        if rendered:
            return rendered
        fallback = location_value.get("fullLocation") or location_value.get("name")
        if isinstance(fallback, str) and fallback.strip():
            return fallback.strip()
    elif isinstance(location_value, str) and location_value.strip():
        return location_value.strip()

    locations_value = job.get("locations")
    if isinstance(locations_value, list) and locations_value:
        first = locations_value[0]
        if isinstance(first, dict):
            parts = [first.get(key) for key in ("city", "region", "country")]
            rendered = ", ".join(str(part).strip() for part in parts if part)
            if rendered:
                return rendered
    return None


def extract_workable_public_api(
    accumulator: AnalysisAccumulator,
    session: Any,
    metadata: URLMetadata,
) -> None:
    if not metadata.org or not metadata.job_id:
        return

    account_url = (
        "https://apply.workable.com/api/v1/accounts/"
        f"{quote(metadata.org, safe='')}"
    )
    jobs_url = (
        "https://apply.workable.com/api/v3/accounts/"
        f"{quote(metadata.org, safe='')}/jobs"
    )

    try:
        account_payload = fetch_json_request(
            session,
            "GET",
            account_url,
            timeout=WORKABLE_API_TIMEOUT_SECONDS,
        )
    except HTTPRequestError:
        account_payload = None

    if isinstance(account_payload, dict):
        accumulator.set_if_missing("company", account_payload.get("name"))
        if account_payload.get("uid"):
            accumulator.add_hidden("workable_account_uid", account_payload.get("uid"))
        if account_payload.get("url"):
            accumulator.add_hidden("company_url", account_payload.get("url"))

    payload = fetch_json_request(
        session,
        "POST",
        jobs_url,
        payload={},
        timeout=WORKABLE_API_TIMEOUT_SECONDS,
    )
    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, list):
        return

    job = next(
        (
            item
            for item in results
            if isinstance(item, dict)
            and metadata.job_id
            in {
                str(item.get("shortcode")) if item.get("shortcode") else None,
                str(item.get("id")) if item.get("id") is not None else None,
                str(item.get("code")) if item.get("code") else None,
            }
        ),
        None,
    )
    if not isinstance(job, dict):
        return

    accumulator.set_preferred("title", job.get("title"))
    location = render_workable_location(job)
    if location:
        accumulator.set_preferred("location", location)

    workplace = job.get("workplace")
    if isinstance(workplace, str):
        accumulator.add_hidden("workplace", workplace)
    elif job.get("remote") is True:
        accumulator.add_hidden("workplace", "remote")

    employment_type = job.get("type")
    if isinstance(employment_type, str) and employment_type.strip():
        accumulator.set_preferred("employment_type", employment_type.strip())

    departments = job.get("department")
    if isinstance(departments, list) and departments:
        accumulator.add_hidden("department", ", ".join(str(item) for item in departments))

    approval_status = job.get("approvalStatus")
    if approval_status:
        accumulator.add_hidden("approval_status", approval_status)

    accumulator.add_date(
        job.get("published"),
        source="workable.api",
        field="published",
        kind="posted",
        reliability="high",
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
                req_id = (
                    str(data.get("req_id")) if data.get("req_id") is not None else None
                )
                slug = str(data.get("slug")) if data.get("slug") is not None else None
                matches = metadata.job_id in {req_id, slug}
                if not matches and apply_url:
                    matches = normalized_url_path(apply_url) == original_path
                if not matches:
                    continue

                accumulator.set_preferred("title", data.get("title"))
                accumulator.set_preferred("company", data.get("hiring_organization"))
                accumulator.set_preferred(
                    "location", data.get("full_location") or data.get("location_name")
                )
                accumulator.set_preferred(
                    "employment_type", data.get("employment_type")
                )
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


def extract_dover_api(
    accumulator: AnalysisAccumulator, session: Any, metadata: URLMetadata
) -> None:
    if not metadata.job_id:
        return

    api_url = (
        f"https://app.dover.com/api/v1/inbound/application-portal-job/{metadata.job_id}"
    )
    try:
        payload = fetch_json(session, api_url)
    except HTTPRequestError as exc:
        accumulator.add_warning(f"Dover API fallback failed: {exc}")
        return

    accumulator.set_preferred("title", payload.get("title"))
    accumulator.set_preferred("company", payload.get("client_name"))

    locations = payload.get("locations")
    if isinstance(locations, list) and locations:
        location_names = [
            item.get("name")
            for item in locations
            if isinstance(item, dict) and item.get("name")
        ]
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
        accumulator.set_preferred(
            "employment_type", compensation.get("employment_type")
        )
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


def extract_bamboohr_api(
    accumulator: AnalysisAccumulator, session: Any, metadata: URLMetadata
) -> None:
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
        parts = [
            location.get("city"),
            location.get("state"),
            location.get("addressCountry"),
        ]
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


def maybe_detect_html_platform(
    url: str, html: str, metadata: URLMetadata
) -> URLMetadata:
    if (
        metadata.platform == "unknown"
        and "careers-static.pageuppeople.com" in html
        and 'id="job-content"' in html
    ):
        parsed = urlparse(url)
        segments = [segment for segment in parsed.path.split("/") if segment]
        job_id = None
        if "job" in segments:
            job_index = segments.index("job")
            if len(segments) > job_index + 1:
                job_id = segments[job_index + 1]
        return URLMetadata(
            platform="pageup",
            org=parsed.netloc.lower(),
            job_id=job_id,
        )
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
        return URLMetadata(
            platform="successfactors",
            org=parsed.netloc.lower(),
            job_id=job_id,
            extra=extra,
        )
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


def extract_successfactors_itemprop_date(
    accumulator: AnalysisAccumulator, html: str
) -> None:
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
                    if (
                        metadata.job_id
                        and metadata.job_id not in link
                        and slug not in link
                    ):
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


def extract_pageup_html(accumulator: AnalysisAccumulator, html: str) -> None:
    title_match = re.search(
        r'<h1[^>]+id=["\']job-title["\'][^>]*>(.*?)</h1>',
        html,
        re.IGNORECASE | re.DOTALL,
    )
    if title_match:
        title = re.sub(r"<[^>]+>", " ", title_match.group(1))
        title = re.sub(r"\s+", " ", unescape(title)).strip()
        if title:
            accumulator.set_preferred("title", title)

    if not accumulator.title:
        meta = extract_meta_tags(html)
        accumulator.set_if_missing("title", meta.get("og:title") or meta.get("title"))

    advertised_match = re.search(
        r"<b>\s*Advertised:\s*</b>\s*<span[^>]+class=[\"']open-date[\"'][^>]*>\s*<time[^>]+datetime=[\"']([^\"']+)",
        html,
        re.IGNORECASE,
    )
    if advertised_match:
        accumulator.add_date(
            advertised_match.group(1).strip(),
            source="pageup.html",
            field="Advertised",
            kind="posted",
            reliability="high",
        )
    else:
        visible_advertised = re.search(
            r"Advertised:\s*(?:<[^>]+>\s*)*([^<\n]+)",
            html,
            re.IGNORECASE,
        )
        if visible_advertised:
            accumulator.add_date(
                visible_advertised.group(1).strip(),
                source="pageup.html",
                field="Advertised",
                kind="posted",
                reliability="medium",
            )

    close_match = re.search(
        r"<b>\s*Applications close:\s*</b>\s*<span[^>]+class=[\"']close-date[\"'][^>]*>\s*<time[^>]+datetime=[\"']([^\"']+)",
        html,
        re.IGNORECASE,
    )
    if close_match:
        accumulator.add_date(
            close_match.group(1).strip(),
            source="pageup.html",
            field="Applications close",
            kind="expiry",
            reliability="medium",
        )


def extract_avature_feed_or_sitemap(
    accumulator: AnalysisAccumulator,
    session: Any,
    metadata: URLMetadata,
    original_url: str,
    html: str,
) -> None:
    html = html or ""
    parsed = urlparse(original_url)
    portal = metadata.extra.get("portal")
    if not portal:
        segments = [segment for segment in parsed.path.split("/") if segment]
        if segments:
            portal = segments[0]
    if not portal:
        portal_match = re.search(
            r'avature\.portal\.id[^>]*content=["\']([^"\']+)', html, re.IGNORECASE
        )
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


def extract_amazon_jobs_api(
    accumulator: AnalysisAccumulator, session: Any, metadata: URLMetadata
) -> None:
    if not metadata.job_id:
        return

    queries = [str(metadata.job_id)]
    slug = metadata.extra.get("job_slug")
    if isinstance(slug, str) and slug.strip():
        slug_query = slug.replace("-", " ").strip()
        if slug_query and slug_query not in queries:
            queries.append(slug_query)

    jobs: list[dict[str, Any]] = []
    for query in queries:
        api_url = f"https://www.amazon.jobs/en/search.json?base_query={quote(query, safe='')}"
        try:
            payload = fetch_json(session, api_url)
        except HTTPRequestError as exc:
            accumulator.add_warning(f"Amazon.jobs API fallback failed: {exc}")
            continue

        candidate_jobs = payload.get("jobs") if isinstance(payload, dict) else None
        if isinstance(candidate_jobs, list) and candidate_jobs:
            jobs = [item for item in candidate_jobs if isinstance(item, dict)]
            if jobs:
                break

    if not jobs:
        return

    job_slug = str(slug) if isinstance(slug, str) else None
    job = next(
        (
            item
            for item in jobs
            if str(item.get("id")) == str(metadata.job_id)
            or str(item.get("id_icims")) == str(metadata.job_id)
            or (
                job_slug
                and isinstance(item.get("job_path"), str)
                and item.get("job_path", "").rstrip("/").split("/")[-1] == job_slug
                and str(item.get("id")) == str(metadata.job_id)
            )
        ),
        None,
    )
    if job is None and job_slug:
        exact_slug_matches = [
            item
            for item in jobs
            if isinstance(item.get("job_path"), str)
            and item.get("job_path", "").rstrip("/").split("/")[-1] == job_slug
        ]
        if len(exact_slug_matches) == 1:
            job = exact_slug_matches[0]
    if job is None:
        job = jobs[0]
    if not isinstance(job, dict):
        return

    accumulator.set_preferred("title", job.get("title"))
    accumulator.set_preferred("company", "Amazon")
    accumulator.set_preferred(
        "location", job.get("normalized_location") or job.get("location")
    )
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


def extract_stripe_greenhouse(
    accumulator: AnalysisAccumulator, session: Any, metadata: URLMetadata
) -> None:
    if not metadata.job_id:
        return

    api_url = f"https://boards-api.greenhouse.io/v1/boards/stripe/jobs/{quote(metadata.job_id, safe='')}"
    try:
        payload = fetch_json(
            session, api_url, timeout=STRIPE_GREENHOUSE_API_TIMEOUT_SECONDS
        )
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
    requisitions = (
        items[0].get("requisitionList") if isinstance(items[0], dict) else None
    )
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


def extract_bendingspoons_objectid(
    accumulator: AnalysisAccumulator, metadata: URLMetadata
) -> None:
    if not metadata.job_id or not re.fullmatch(
        r"[a-f0-9]{24}", metadata.job_id, re.IGNORECASE
    ):
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


def extract_gem_job_board_api(
    accumulator: AnalysisAccumulator, session: Any, metadata: URLMetadata
) -> None:
    if not metadata.org:
        return

    api_url = (
        f"https://api.gem.com/job_board/v0/{quote(metadata.org, safe='')}/job_posts/"
    )
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

    job = next(
        (item for item in payload if isinstance(item, dict) and matches_job(item)), None
    )
    if job is None:
        job = next((item for item in payload if isinstance(item, dict)), None)
    if not isinstance(job, dict):
        return

    accumulator.set_preferred("title", job.get("title"))
    accumulator.set_if_missing(
        "company", metadata.org.replace("-", " ").title() if metadata.org else None
    )
    if isinstance(job.get("location"), dict):
        accumulator.set_preferred("location", job["location"].get("name"))

    employment_type = job.get("employment_type")
    if isinstance(employment_type, str):
        accumulator.set_preferred(
            "employment_type", employment_type.replace("_", " ").title()
        )

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


def extract_recruitee_api(
    accumulator: AnalysisAccumulator, session: Any, metadata: URLMetadata
) -> None:
    if not metadata.org or not metadata.job_id:
        return

    api_url = f"https://{metadata.org}.recruitee.com/api/offers/{quote(metadata.job_id, safe='')}"
    try:
        payload = fetch_json(session, api_url)
    except HTTPRequestError as exc:
        accumulator.add_warning(f"Recruitee API fallback failed: {exc}")
        return

    offer = payload.get("offer") if isinstance(payload, dict) else None
    if not isinstance(offer, dict):
        return

    accumulator.set_preferred("title", offer.get("title"))
    accumulator.set_preferred("company", offer.get("company_name"))
    accumulator.set_preferred("location", offer.get("location"))

    if offer.get("remote"):
        accumulator.set_preferred("employment_type", "Remote")
    elif offer.get("hybrid"):
        accumulator.set_preferred("employment_type", "Hybrid")
    elif offer.get("on_site"):
        accumulator.set_preferred("employment_type", "On-site")

    accumulator.add_hidden("recruitee_offer_id", offer.get("id"))
    accumulator.add_hidden("department", offer.get("department"))
    accumulator.add_hidden("employment_type_code", offer.get("employment_type_code"))
    accumulator.add_hidden("experience_code", offer.get("experience_code"))
    accumulator.add_hidden("category_code", offer.get("category_code"))
    accumulator.add_hidden("guid", offer.get("guid"))

    accumulator.add_date(
        offer.get("published_at"),
        source="recruitee.api",
        field="published_at",
        kind="posted",
        reliability="high",
    )
    if not offer.get("published_at"):
        accumulator.add_date(
            offer.get("created_at"),
            source="recruitee.api",
            field="created_at",
            kind="posted",
            reliability="medium",
            note="Recruitee created_at reflects when the offer record was created; prefer published_at when available.",
        )
    accumulator.add_date(
        offer.get("updated_at"),
        source="recruitee.api",
        field="updated_at",
        kind="refresh",
        reliability="medium",
        note="Recruitee updated_at reflects edits or freshness, not original posting time.",
    )


def extract_personio_xml_fallback(
    accumulator: AnalysisAccumulator,
    session: Any,
    metadata: URLMetadata,
    original_url: str,
) -> None:
    if not metadata.job_id:
        return
    if any(
        candidate.kind in {"posted", "published"} for candidate in accumulator.all_dates
    ):
        return

    parsed = urlparse(original_url)
    language = parse_qs(parsed.query).get("language", [None])[0] or "en"
    xml_url = (
        f"{parsed.scheme}://{parsed.netloc}/xml?language={quote(language, safe='')}"
    )
    try:
        xml_text = fetch_text(session, xml_url)
    except HTTPRequestError as exc:
        accumulator.add_warning(f"Personio XML fallback failed: {exc}")
        return

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return

    for position in root.findall("position"):
        if (position.findtext("id") or "").strip() != metadata.job_id:
            continue
        accumulator.set_preferred("title", position.findtext("name"))
        accumulator.set_if_missing("company", position.findtext("subcompany"))
        accumulator.set_if_missing("location", position.findtext("office"))
        accumulator.add_hidden("department", position.findtext("department"))
        accumulator.add_hidden(
            "recruiting_category", position.findtext("recruitingCategory")
        )
        accumulator.add_date(
            position.findtext("createdAt"),
            source="personio.xml",
            field="createdAt",
            kind="posted",
            reliability="high",
        )
        return


def extract_breezy_data_position(accumulator: AnalysisAccumulator, html: str) -> None:
    match = re.search(r'data-position="([^"]+)"', html, re.IGNORECASE | re.DOTALL)
    if not match:
        return

    payload = parse_jsonish(unescape(match.group(1)))
    if not isinstance(payload, dict):
        return

    accumulator.set_preferred("title", payload.get("name"))

    company = payload.get("company")
    if isinstance(company, dict):
        accumulator.set_preferred("company", company.get("name"))

    location = payload.get("location")
    if isinstance(location, dict):
        if location.get("is_remote"):
            accumulator.set_preferred("location", location.get("name") or "Remote")
        else:
            accumulator.set_preferred("location", location.get("name"))

    job_type = payload.get("type")
    if isinstance(job_type, dict):
        accumulator.set_preferred("employment_type", job_type.get("name"))

    accumulator.add_hidden("department", payload.get("department"))
    category = payload.get("category")
    if isinstance(category, dict):
        accumulator.add_hidden("category", category.get("name"))

    accumulator.add_date(
        payload.get("first_publish_date"),
        source="breezy.embedded",
        field="first_publish_date",
        kind="posted",
        reliability="high",
    )
    accumulator.add_date(
        payload.get("last_publish_date"),
        source="breezy.embedded",
        field="last_publish_date",
        kind="refresh",
        reliability="medium",
        note="Breezy last_publish_date reflects the latest refresh or reposting event.",
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
        payload = fetch_json(session, api_url, timeout=WORKDAY_API_TIMEOUT_SECONDS)
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
        accumulator.set_preferred(
            "location", requisition_location.get("descriptor") or location
        )

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


def adp_custom_field_value(
    payload: dict[str, Any], field_group: str, code_value: str
) -> Any | None:
    custom_group = payload.get("customFieldGroup")
    if not isinstance(custom_group, dict):
        return None

    fields = custom_group.get(field_group)
    if not isinstance(fields, list):
        return None

    value_key = {
        "dateFields": "dateValue",
        "stringFields": "stringValue",
        "indicatorFields": "indicatorValue",
        "numberFields": "numberValue",
        "codeFields": "codeValue",
    }.get(field_group)
    if value_key is None:
        return None

    for item in fields:
        if not isinstance(item, dict):
            continue
        name_code = item.get("nameCode")
        if isinstance(name_code, dict) and name_code.get("codeValue") == code_value:
            return item.get(value_key)
    return None


def extract_adp_api(
    accumulator: AnalysisAccumulator,
    session: Any,
    metadata: URLMetadata,
) -> None:
    cid = metadata.org or metadata.extra.get("cid")
    if not cid or not metadata.job_id:
        return

    lang = str(metadata.extra.get("lang") or "en_US")
    params: list[tuple[str, str]] = [
        ("cid", str(cid)),
        ("timeStamp", "1"),
        ("lang", lang),
        ("locale", lang),
    ]
    cc_id = metadata.extra.get("cc_id")
    if cc_id:
        params.append(("ccId", str(cc_id)))

    api_url = (
        "https://workforcenow.adp.com/mascsr/default/careercenter/public/events/"
        f"staffing/v1/job-requisitions/{quote(str(metadata.job_id), safe='')}?{urlencode(params)}"
    )
    payload = fetch_json_request(
        session,
        "GET",
        api_url,
        headers={
            "X-Requested-With": "XMLHttpRequest",
            "Accept-Language": lang,
            "locale": lang,
        },
        timeout=ADP_API_TIMEOUT_SECONDS,
    )
    if not isinstance(payload, dict):
        return

    accumulator.set_preferred("title", payload.get("requisitionTitle"))

    work_level = payload.get("workLevelCode")
    if isinstance(work_level, dict):
        accumulator.set_preferred("employment_type", work_level.get("shortName"))

    requisition_locations = payload.get("requisitionLocations")
    if isinstance(requisition_locations, list) and requisition_locations:
        first = requisition_locations[0]
        if isinstance(first, dict):
            name_code = first.get("nameCode")
            if isinstance(name_code, dict):
                accumulator.set_preferred("location", name_code.get("shortName"))

    if payload.get("clientRequisitionID"):
        accumulator.add_hidden("client_requisition_id", payload.get("clientRequisitionID"))
    if payload.get("itemID"):
        accumulator.add_hidden("item_id", payload.get("itemID"))

    external_job_id = adp_custom_field_value(payload, "stringFields", "ExternalJobID")
    if external_job_id:
        accumulator.add_hidden("external_job_id", external_job_id)
    job_class = adp_custom_field_value(payload, "stringFields", "JobClass")
    if job_class:
        accumulator.add_hidden("job_class", job_class)
    salary_range = adp_custom_field_value(payload, "stringFields", "SalaryRange")
    if salary_range:
        accumulator.add_hidden("salary_range", salary_range)

    accumulator.add_date(
        payload.get("postDate")
        or adp_custom_field_value(payload, "dateFields", "PostingDate"),
        source="adp.api",
        field="postDate",
        kind="posted",
        reliability="high",
    )


def should_use_render_fallback(html: str, accumulator: AnalysisAccumulator) -> bool:
    if any(
        candidate.kind in {"posted", "published"} for candidate in accumulator.all_dates
    ):
        return False
    if not html.strip():
        return True
    lower_html = html.lower()
    thin_markers = (
        "please enable js",
        "cf-challenge",
        "captcha-delivery",
        '<div id="app"',
        '<div id="root"',
    )
    return len(html) < 2500 or any(marker in lower_html for marker in thin_markers)


def extract_dates_from_rendered_text(
    accumulator: AnalysisAccumulator, rendered_text: str
) -> None:
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
        rendered_text = fetch_text(
            session,
            JINA_PREFIX
            + build_normalized_url(accumulator.url)
            .removeprefix("https://")
            .removeprefix("http://"),
        )
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


def path_matches_sitemap(
    target_url: str, candidate_url: str, metadata: URLMetadata
) -> bool:
    target = build_normalized_url(target_url)
    candidate = build_normalized_url(candidate_url)
    if target == candidate:
        return True
    if metadata.job_id and metadata.job_id in candidate_url:
        return True
    return normalized_url_path(target_url) == normalized_url_path(candidate_url)


def extract_sitemap_dates(
    accumulator: AnalysisAccumulator, session: Any, metadata: URLMetadata
) -> None:
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
        if candidate.kind in {"posted", "published"}
        and candidate.reliability in {"high", "medium"}
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


def detect_repost(
    best_date: CandidateDate | None, all_dates: list[CandidateDate]
) -> bool:
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
        key=lambda item: (
            item.date,
            DATE_KIND_PRIORITY[item.kind],
            RELIABILITY_PRIORITY[item.reliability],
        ),
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


def handle_blocked_or_unsupported(
    url: str, metadata: URLMetadata
) -> dict[str, Any] | None:
    normalized_url = build_normalized_url(url)
    accumulator = AnalysisAccumulator(
        url=url, normalized_url=normalized_url, platform=metadata.platform
    )
    if metadata.platform in BLOCKED_PLATFORM_MESSAGES:
        accumulator.add_warning(BLOCKED_PLATFORM_MESSAGES[metadata.platform])
        return build_result(accumulator, status_override="blocked")
    if metadata.platform in UNSUPPORTED_PLATFORM_MESSAGES:
        accumulator.add_warning(UNSUPPORTED_PLATFORM_MESSAGES[metadata.platform])
        return build_result(accumulator, status_override="unsupported")
    return None


def run_extraction_stage(
    accumulator: AnalysisAccumulator,
    stage_label: str,
    extractor: Any,
    *args: Any,
) -> None:
    _emit_progress({"type": "stage", "label": stage_label, "status": "start"})
    try:
        extractor(*args)
        _emit_progress({"type": "stage", "label": stage_label, "status": "ok"})
    except HTTPRequestError as exc:
        accumulator.add_warning(f"{stage_label} failed: {exc}")
        _emit_progress(
            {
                "type": "stage",
                "label": stage_label,
                "status": "warn",
                "detail": str(exc),
            }
        )
    except Exception as exc:
        accumulator.add_warning(f"{stage_label} parser error: {exc}")
        _emit_progress(
            {
                "type": "stage",
                "label": stage_label,
                "status": "warn",
                "detail": str(exc),
            }
        )


def has_credible_posted_signal(accumulator: AnalysisAccumulator) -> bool:
    return any(
        candidate.kind in {"posted", "published"}
        and candidate.reliability in {"high", "medium"}
        for candidate in accumulator.all_dates
    )


def has_strong_native_posted_signal(accumulator: AnalysisAccumulator) -> bool:
    return any(
        candidate.kind in {"posted", "published"}
        and candidate.reliability in {"high", "medium"}
        and SOURCE_PRIORITY.get(candidate.source, 99) <= 1
        for candidate in accumulator.all_dates
    )


def has_comparison_evidence(accumulator: AnalysisAccumulator) -> bool:
    return any(
        candidate.source in COMPARISON_SOURCES for candidate in accumulator.all_dates
    )


def should_run_wayback_fallback(accumulator: AnalysisAccumulator) -> bool:
    if has_comparison_evidence(accumulator):
        return False

    sorted_dates = sorted(
        accumulator.all_dates,
        key=lambda item: (
            item.date,
            DATE_KIND_PRIORITY[item.kind],
            RELIABILITY_PRIORITY[item.reliability],
        ),
    )
    best_date = choose_best_date(sorted_dates)

    if best_date is None:
        return True

    strong_native_signal = has_strong_native_posted_signal(accumulator)

    return not strong_native_signal


def extract_workday_bootstrap(html: str) -> dict[str, Any]:
    window_match = re.search(
        r"window\.workday\s*=\s*window\.workday\s*\|\|\s*\{(.*?)\};",
        html,
        re.DOTALL,
    )
    if not window_match:
        return {}

    snippet = window_match.group(1)
    data: dict[str, Any] = {}

    for key in ("tenant", "siteId", "locale", "requestLocale", "token"):
        match = re.search(rf'{key}\s*:\s*"([^"]+)"', snippet)
        if match:
            data[key] = match.group(1)

    posting_available = re.search(r"postingAvailable\s*:\s*(true|false)", snippet)
    if posting_available:
        data["postingAvailable"] = posting_available.group(1) == "true"

    return data


def analyze_url(
    url: str,
    *,
    session: Any | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    _emit_progress({"type": "start", "url": url})
    validated_url = validate_url(url)
    active_session = session or build_session()
    budget = RequestBudget.start(TOTAL_ANALYSIS_BUDGET_SECONDS)
    session_with_budget = BudgetedSession(active_session, budget)
    metadata = detect_platform(validated_url)
    _emit_progress({"type": "platform", "platform": metadata.platform})

    blocked_result = handle_blocked_or_unsupported(validated_url, metadata)
    if blocked_result is not None:
        return blocked_result

    accumulator = AnalysisAccumulator(
        url=validated_url,
        normalized_url=build_normalized_url(validated_url),
        platform=metadata.platform,
    )

    prefetch_warning_count = len(accumulator.warnings)
    if metadata.platform == "lever":
        extract_lever_api(accumulator, session_with_budget, metadata)
    elif metadata.platform == "greenhouse":
        if metadata.extra.get("resolver") == "stripe":
            extract_stripe_greenhouse(
                accumulator, session_with_budget, metadata
            )
        elif metadata.org and metadata.job_id:
            extract_greenhouse_api(accumulator, session_with_budget, metadata)
    elif metadata.platform == "ashby":
        extract_ashby_api(
            accumulator,
            session_with_budget,
            metadata,
            validated_url,
        )
    if not has_strong_native_posted_signal(accumulator):
        del accumulator.warnings[prefetch_warning_count:]

    page_fetch_error: HTTPRequestError | None = None
    html = ""
    page_url = validated_url
    page_fetch_timeout = (
        ENRICHMENT_FETCH_TIMEOUT_SECONDS
        if has_strong_native_posted_signal(accumulator)
        else DEFAULT_TIMEOUT_SECONDS
    )
    _emit_progress({"type": "stage", "label": "Page fetch", "status": "start"})
    try:
        page_response = session_with_budget.get(
            validated_url, timeout=page_fetch_timeout
        )
        page_response.raise_for_status()
        html = page_response.text
        page_url = getattr(page_response, "final_url", None) or validated_url
        _emit_progress({"type": "stage", "label": "Page fetch", "status": "ok"})
    except HTTPRequestError as exc:
        page_fetch_error = exc
        accumulator.add_warning(
            f"Primary page fetch failed: {exc}. Falling back to ATS APIs, render fallback, sitemap, and archive signals."
        )
        _emit_progress(
            {
                "type": "stage",
                "label": "Page fetch",
                "status": "warn",
                "detail": str(exc),
            }
        )

    if html:
        fetched_metadata = detect_platform(page_url)
        if fetched_metadata.platform != "unknown":
            metadata = fetched_metadata
        elif urlparse(page_url).netloc.lower() != urlparse(validated_url).netloc.lower():
            metadata = fetched_metadata
        previous_platform = metadata.platform
        metadata = maybe_detect_html_platform(page_url, html, metadata)
        if metadata.platform != previous_platform:
            _emit_progress({"type": "platform", "platform": metadata.platform})
        run_extraction_stage(
            accumulator, "JSON-LD extraction", extract_jsonld, accumulator, html
        )
        run_extraction_stage(
            accumulator,
            "Meta/OpenGraph extraction",
            extract_meta_and_open_graph,
            accumulator,
            html,
        )
        run_extraction_stage(
            accumulator, "Regex date extraction", extract_regex_dates, accumulator, html
        )
        run_extraction_stage(
            accumulator,
            "Embedded JSON extraction",
            extract_embedded_json,
            accumulator,
            html,
        )
        accumulator.platform = metadata.platform

    if metadata.platform == "lever":
        if not has_strong_native_posted_signal(accumulator):
            run_extraction_stage(
                accumulator,
                "Lever API fallback",
                extract_lever_api,
                accumulator,
                session_with_budget,
                metadata,
            )
    elif metadata.platform == "greenhouse":
        if html:
            run_extraction_stage(
                accumulator,
                "Greenhouse HTML fallback",
                detect_from_greenhouse_html,
                accumulator,
                html,
                page_url,
                metadata,
            )
        if not has_strong_native_posted_signal(accumulator):
            if metadata.extra.get("resolver") == "stripe":
                run_extraction_stage(
                    accumulator,
                    "Stripe Greenhouse fallback",
                    extract_stripe_greenhouse,
                    accumulator,
                    session_with_budget,
                    metadata,
                )
            elif metadata.org and metadata.job_id:
                run_extraction_stage(
                    accumulator,
                    "Greenhouse API fallback",
                    extract_greenhouse_api,
                    accumulator,
                    session_with_budget,
                    metadata,
                )
    elif metadata.platform == "ashby":
        if html or not has_strong_native_posted_signal(accumulator):
            run_extraction_stage(
                accumulator,
                "Ashby API fallback",
                extract_ashby_api,
                accumulator,
                session_with_budget,
                metadata,
                validated_url,
                html,
            )
    elif metadata.platform == "recruitee":
        run_extraction_stage(
            accumulator,
            "Recruitee API fallback",
            extract_recruitee_api,
            accumulator,
            session_with_budget,
            metadata,
        )
    elif metadata.platform == "smartrecruiters":
        run_extraction_stage(
            accumulator,
            "SmartRecruiters API fallback",
            extract_smartrecruiters_api,
            accumulator,
            session_with_budget,
            metadata,
        )
    elif metadata.platform == "pageup" and html:
        run_extraction_stage(
            accumulator,
            "PageUp HTML extraction",
            extract_pageup_html,
            accumulator,
            html,
        )
    elif metadata.platform == "personio":
        run_extraction_stage(
            accumulator,
            "Personio XML fallback",
            extract_personio_xml_fallback,
            accumulator,
            session_with_budget,
            metadata,
            validated_url,
        )
    elif metadata.platform == "rippling" and html:
        run_extraction_stage(
            accumulator,
            "Rippling embedded extraction",
            extract_rippling_embedded,
            accumulator,
            html,
        )
    elif metadata.platform == "breezy" and html:
        run_extraction_stage(
            accumulator,
            "Breezy embedded extraction",
            extract_breezy_data_position,
            accumulator,
            html,
        )
    elif metadata.platform == "workable":
        if html:
            run_extraction_stage(
                accumulator,
                "Workable embedded extraction",
                extract_workable_embedded,
                accumulator,
                html,
                metadata,
            )
        if metadata.org and not has_credible_posted_signal(accumulator):
            run_extraction_stage(
                accumulator,
                "Workable public API fallback",
                extract_workable_public_api,
                accumulator,
                session_with_budget,
                metadata,
            )
    elif metadata.platform == "dayforce" and html:
        run_extraction_stage(
            accumulator,
            "Dayforce Next.js extraction",
            extract_dayforce_next_data,
            accumulator,
            html,
        )
    elif metadata.platform == "icims" and html:
        run_extraction_stage(
            accumulator,
            "iCIMS API fallback",
            extract_icims_api,
            accumulator,
            session_with_budget,
            metadata,
            html,
            validated_url,
        )
    elif metadata.platform == "dover":
        run_extraction_stage(
            accumulator,
            "Dover API fallback",
            extract_dover_api,
            accumulator,
            session_with_budget,
            metadata,
        )
    elif metadata.platform == "bamboohr":
        run_extraction_stage(
            accumulator,
            "BambooHR API fallback",
            extract_bamboohr_api,
            accumulator,
            session_with_budget,
            metadata,
        )
    elif metadata.platform == "brassring" and html:
        run_extraction_stage(
            accumulator,
            "Brassring HTML extraction",
            extract_brassring_html,
            accumulator,
            html,
        )
    elif metadata.platform == "successfactors" and html:
        run_extraction_stage(
            accumulator,
            "SuccessFactors RSS fallback",
            extract_successfactors_rss,
            accumulator,
            session_with_budget,
            metadata,
            validated_url,
            html,
        )
    elif metadata.platform == "gem":
        run_extraction_stage(
            accumulator,
            "Gem API fallback",
            extract_gem_job_board_api,
            accumulator,
            session_with_budget,
            metadata,
        )
    elif metadata.platform == "custom_backend":
        resolver = metadata.extra.get("resolver")
        if resolver == "amazon_jobs":
            run_extraction_stage(
                accumulator,
                "Amazon.jobs API fallback",
                extract_amazon_jobs_api,
                accumulator,
                session_with_budget,
                metadata,
            )
        elif resolver == "bending_spoons":
            run_extraction_stage(
                accumulator,
                "Bending Spoons ObjectID extraction",
                extract_bendingspoons_objectid,
                accumulator,
                metadata,
            )
    elif metadata.platform == "workday":
        workday_bootstrap = extract_workday_bootstrap(html) if html else {}
        if workday_bootstrap.get("tenant") and not metadata.org:
            metadata.org = str(workday_bootstrap["tenant"])
        if workday_bootstrap.get("siteId") and not metadata.extra.get("site"):
            metadata.extra["site"] = str(workday_bootstrap["siteId"])
        if "postingAvailable" in workday_bootstrap:
            accumulator.add_hidden(
                "workday_posting_available", workday_bootstrap["postingAvailable"]
            )
        if workday_bootstrap.get("postingAvailable") is False:
            accumulator.add_warning(
                "Workday page indicates the posting is no longer available."
            )
        else:
            run_extraction_stage(
                accumulator,
                "Workday CXS fallback",
                extract_workday_api,
                accumulator,
                session_with_budget,
                metadata,
                validated_url,
            )
    elif metadata.platform == "adp":
        run_extraction_stage(
            accumulator,
            "ADP API fallback",
            extract_adp_api,
            accumulator,
            session_with_budget,
            metadata,
        )
    elif metadata.platform == "ukg_pro" and html:
        run_extraction_stage(
            accumulator,
            "UKG Pro embedded extraction",
            extract_ukg_pro_embedded,
            accumulator,
            html,
        )
    elif metadata.platform == "oracle_hcm":
        if metadata.extra.get("resolver") == "goldman_sachs":
            run_extraction_stage(
                accumulator,
                "Goldman Sachs Oracle fallback",
                extract_goldman_sachs_oracle,
                accumulator,
                session_with_budget,
                metadata,
            )
        else:
            run_extraction_stage(
                accumulator,
                "Oracle HCM fallback",
                extract_oracle_hcm_api,
                accumulator,
                session_with_budget,
                metadata,
                validated_url,
            )
    elif metadata.platform == "jobvite" and html:
        run_extraction_stage(
            accumulator,
            "Jobvite XML fallback",
            extract_jobvite_xml,
            accumulator,
            session_with_budget,
            metadata,
            html,
        )
    elif metadata.platform == "avature":
        run_extraction_stage(
            accumulator,
            "Avature feed/sitemap fallback",
            extract_avature_feed_or_sitemap,
            accumulator,
            session_with_budget,
            metadata,
            validated_url,
            html or "",
        )

    if should_use_render_fallback(html, accumulator):
        if budget.can_run(MIN_BUDGET_FOR_RENDER_SECONDS):
            run_extraction_stage(
                accumulator,
                "Jina render fallback",
                extract_jina_render,
                accumulator,
                session_with_budget,
            )
        else:
            accumulator.add_warning(
                "Skipped Jina render fallback due to remaining analysis budget."
            )

    platform_capability = get_platform_capability(metadata.platform)
    skip_comparison_fallbacks = (
        platform_capability["integration"] == "direct"
        and has_strong_native_posted_signal(accumulator)
    ) or (
        metadata.platform == "successfactors"
        and has_credible_posted_signal(accumulator)
    )

    if skip_comparison_fallbacks:
        pass
    elif budget.can_run(MIN_BUDGET_FOR_SITEMAP_SECONDS):
        run_extraction_stage(
            accumulator,
            "Sitemap fallback",
            extract_sitemap_dates,
            accumulator,
            session_with_budget,
            metadata,
        )
    else:
        accumulator.add_warning(
            "Skipped sitemap fallback due to remaining analysis budget."
        )

    should_run_wayback = not skip_comparison_fallbacks and should_run_wayback_fallback(
        accumulator
    )

    if should_run_wayback and budget.can_run(MIN_BUDGET_FOR_WAYBACK_SECONDS):
        run_extraction_stage(
            accumulator,
            "Wayback fallback",
            extract_wayback,
            accumulator,
            session_with_budget,
        )
    elif should_run_wayback:
        accumulator.add_warning(
            "Skipped Wayback fallback due to remaining analysis budget."
        )

    if budget.exhausted():
        accumulator.add_warning(
            "Analysis time budget exhausted before all fallbacks could run."
        )

    result = build_result(accumulator, today=today)
    if (
        result["status"] == "no_date"
        and page_fetch_error is not None
        and not accumulator.all_dates
    ):
        raise PageFetchError(
            f"Unable to fetch job page: {validated_url}"
        ) from page_fetch_error
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
        prog="howoldisthisjob",
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
