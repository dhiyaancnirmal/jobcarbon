import socket
import unittest
import warnings
from io import BytesIO
from email.message import Message
from urllib.error import HTTPError, URLError

import jobcarbon


class FakeHTTPStream:
    def __init__(self, body: str, status: int = 200) -> None:
        self._body = body.encode("utf-8")
        self.status = status
        self.headers = Message()
        self.headers.add_header("Content-Type", "application/json; charset=utf-8")

    def read(self) -> bytes:
        return self._body

    def getcode(self) -> int:
        return self.status

    def __enter__(self) -> "FakeHTTPStream":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class JobcarbonUnitTests(unittest.TestCase):
    def test_detect_platform_parses_supported_hosts(self) -> None:
        lever = jobcarbon.detect_platform(
            "https://jobs.lever.co/skio/bbdd5a7b-652a-43ad-b92e-58f4e970c694"
        )
        greenhouse = jobcarbon.detect_platform(
            "https://job-boards.greenhouse.io/applytogreenspark/jobs/4169702004"
        )
        ashby = jobcarbon.detect_platform(
            "https://jobs.ashbyhq.com/glimpse/767a3a59-53d6-4306-afae-6b05a265ba82"
        )
        smartrecruiters = jobcarbon.detect_platform(
            "https://jobs.smartrecruiters.com/ServiceNow/744000103790775-software-engineer"
        )
        rippling = jobcarbon.detect_platform(
            "https://ats.rippling.com/rippling/jobs/bda12f6a-6afc-45af-8e6a-b0056facf15c"
        )
        dover = jobcarbon.detect_platform(
            "https://app.dover.com/apply/netnow/2bfb58ac-c3f9-46c6-8f94-ceb6b4950cff"
        )
        workable = jobcarbon.detect_platform(
            "https://jobs.workable.com/view/5Sz2Mnf9VdJsXnPCvoYudJ/captain---n-u-piraeus-port"
        )
        icims = jobcarbon.detect_platform(
            "https://globalcareers-customer0.icims.com/jobs/6341/login"
        )
        workday = jobcarbon.detect_platform(
            "https://walmart.wd5.myworkdayjobs.com/en-US/WalmartExternal/job/Staff--Software-Engineer_R-2403353"
        )

        self.assertEqual((lever.platform, lever.org, lever.job_id), ("lever", "skio", "bbdd5a7b-652a-43ad-b92e-58f4e970c694"))
        self.assertEqual((greenhouse.platform, greenhouse.org, greenhouse.job_id), ("greenhouse", "applytogreenspark", "4169702004"))
        self.assertEqual((ashby.platform, ashby.org, ashby.job_id), ("ashby", "glimpse", "767a3a59-53d6-4306-afae-6b05a265ba82"))
        self.assertEqual((smartrecruiters.platform, smartrecruiters.org, smartrecruiters.job_id), ("smartrecruiters", "ServiceNow", "744000103790775"))
        self.assertEqual((rippling.platform, rippling.org, rippling.job_id), ("rippling", "rippling", "bda12f6a-6afc-45af-8e6a-b0056facf15c"))
        self.assertEqual((dover.platform, dover.org, dover.job_id), ("dover", "netnow", "2bfb58ac-c3f9-46c6-8f94-ceb6b4950cff"))
        self.assertEqual((workable.platform, workable.org, workable.job_id), ("workable", None, "5Sz2Mnf9VdJsXnPCvoYudJ"))
        self.assertEqual((icims.platform, icims.job_id), ("icims", "6341"))
        self.assertEqual(workday.platform, "workday")

    def test_extract_job_postings_handles_object_array_and_graph(self) -> None:
        html = """
        <script type="application/ld+json">
        {"@context":"https://schema.org","@type":"Organization","name":"Example"}
        </script>
        <script type="application/ld+json">
        [{"@type":"JobPosting","datePosted":"2024-01-02"},{"@type":"Thing"}]
        </script>
        <script type="application/ld+json">
        {"@graph":[{"@type":"WebPage"},{"@type":["JobPosting"],"datePosted":"2024-02-03"}]}
        </script>
        """

        postings = jobcarbon.extract_job_postings_from_html(html)

        self.assertEqual(len(postings), 2)
        self.assertEqual(postings[0]["datePosted"], "2024-01-02")
        self.assertEqual(postings[1]["datePosted"], "2024-02-03")

    def test_normalize_date_supports_multiple_formats(self) -> None:
        self.assertEqual(jobcarbon.normalize_date("2024-03-04T10:11:12Z"), "2024-03-04")
        self.assertEqual(jobcarbon.normalize_date(1710151200000), "2024-03-11")
        self.assertEqual(jobcarbon.normalize_date("20210405112233"), "2021-04-05")
        self.assertEqual(jobcarbon.normalize_date("March 4, 2024"), "2024-03-04")
        self.assertEqual(jobcarbon.normalize_date("03/04/2024"), "2024-03-04")

    def test_choose_best_date_prefers_oldest_credible_posted_signal(self) -> None:
        dates = [
            jobcarbon.CandidateDate("2024-02-01", "meta", "article:published_time", "published", "medium"),
            jobcarbon.CandidateDate("2024-01-10", "jsonld.jobposting", "datePosted", "posted", "high"),
            jobcarbon.CandidateDate("2023-12-20", "sitemap", "lastmod", "crawl", "low"),
            jobcarbon.CandidateDate("2023-12-01", "wayback.cdx", "first_snapshot", "archive", "low"),
        ]

        chosen = jobcarbon.choose_best_date(dates)

        self.assertIsNotNone(chosen)
        self.assertEqual(chosen.date, "2024-01-10")
        self.assertEqual(chosen.source, "jsonld.jobposting")

    def test_detect_repost_flags_newer_refresh_signals(self) -> None:
        oldest = jobcarbon.CandidateDate("2024-01-01", "jsonld.jobposting", "datePosted", "posted", "high")
        dates = [
            oldest,
            jobcarbon.CandidateDate("2024-03-20", "greenhouse.api", "updated_at", "refresh", "medium"),
        ]
        self.assertTrue(jobcarbon.detect_repost(oldest, dates))

    def test_http_session_retries_transient_errors(self) -> None:
        calls = {"count": 0}
        sleep_calls = []

        def opener(request, timeout):
            calls["count"] += 1
            if calls["count"] < 3:
                raise URLError(socket.timeout("timed out"))
            return FakeHTTPStream('{"ok": true}')

        session = jobcarbon.HTTPSession(opener=opener, sleeper=sleep_calls.append)

        response = session.get("https://example.com", timeout=5)

        self.assertEqual(response.json(), {"ok": True})
        self.assertEqual(calls["count"], 3)
        self.assertEqual(sleep_calls, [0.5, 1.0])

    def test_http_session_does_not_retry_non_retryable_http_errors(self) -> None:
        calls = {"count": 0}

        def opener(request, timeout):
            calls["count"] += 1
            raise HTTPError(
                url=request.full_url,
                code=404,
                msg="Not Found",
                hdrs=None,
                fp=BytesIO(b""),
            )

        session = jobcarbon.HTTPSession(opener=opener, sleeper=lambda _: None)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ResourceWarning)
            with self.assertRaises(jobcarbon.HTTPRequestError) as ctx:
                session.get("https://example.com/missing", timeout=5)

        self.assertEqual(calls["count"], 1)
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertFalse(ctx.exception.retryable)


if __name__ == "__main__":
    unittest.main()
