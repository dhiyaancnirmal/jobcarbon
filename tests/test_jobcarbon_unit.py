import socket
import unittest
from datetime import date
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
    def test_detect_ats_parses_supported_hosts(self) -> None:
        lever = jobcarbon.detect_ats(
            "https://jobs.lever.co/skio/bbdd5a7b-652a-43ad-b92e-58f4e970c694"
        )
        greenhouse = jobcarbon.detect_ats(
            "https://job-boards.greenhouse.io/applytogreenspark/jobs/4169702004"
        )
        ashby = jobcarbon.detect_ats(
            "https://jobs.ashbyhq.com/glimpse/767a3a59-53d6-4306-afae-6b05a265ba82"
        )

        self.assertEqual((lever.ats, lever.org, lever.job_id), ("lever", "skio", "bbdd5a7b-652a-43ad-b92e-58f4e970c694"))
        self.assertEqual((greenhouse.ats, greenhouse.org, greenhouse.job_id), ("greenhouse", "applytogreenspark", "4169702004"))
        self.assertEqual((ashby.ats, ashby.org, ashby.job_id), ("ashby", "glimpse", "767a3a59-53d6-4306-afae-6b05a265ba82"))

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

    def test_normalize_date_supports_iso_epoch_and_wayback_timestamp(self) -> None:
        self.assertEqual(jobcarbon.normalize_date("2024-03-04T10:11:12Z"), "2024-03-04")
        self.assertEqual(jobcarbon.normalize_date(1710151200000), "2024-03-11")
        self.assertEqual(jobcarbon.normalize_date("20210405112233"), "2021-04-05")

    def test_age_days_uses_supplied_reference_day(self) -> None:
        self.assertEqual(jobcarbon.age_days("2024-03-10", today=date(2024, 3, 15)), 5)

    def test_jsonld_detection_prefers_date_posted(self) -> None:
        html = """
        <script type="application/ld+json">
        {"@type":"JobPosting","datePosted":"2024-02-20","validThrough":"2024-03-20"}
        </script>
        """
        evidence = []

        result = jobcarbon.detect_from_jsonld(html, evidence, today=date(2024, 3, 1))

        self.assertIsNotNone(result)
        self.assertEqual(result["estimated_posted"], "2024-02-20")
        self.assertEqual(result["method"], "jsonld.jobposting.datePosted")
        self.assertEqual([item["field"] for item in evidence], ["datePosted", "validThrough"])

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
                fp=None,
            )

        session = jobcarbon.HTTPSession(opener=opener, sleeper=lambda _: None)

        with self.assertRaises(jobcarbon.HTTPRequestError) as ctx:
            session.get("https://example.com/missing", timeout=5)

        self.assertEqual(calls["count"], 1)
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertFalse(ctx.exception.retryable)


if __name__ == "__main__":
    unittest.main()
