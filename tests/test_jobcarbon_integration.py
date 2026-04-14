import json
import unittest
from pathlib import Path
from typing import Any

import jobcarbon


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_text(name: str) -> str:
    return (FIXTURES_DIR / name).read_text()


def load_json(name: str) -> Any:
    return json.loads(load_text(name))


class FakeResponse:
    def __init__(self, *, text: str = "", json_data: Any = None, status_code: int = 200) -> None:
        self.text = text
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise jobcarbon.HTTPRequestError(f"HTTP {self.status_code}")

    def json(self) -> Any:
        return self._json_data


class FakeSession:
    def __init__(self, responses: dict[str, FakeResponse]) -> None:
        self.responses = responses

    def get(self, url: str, timeout: int) -> FakeResponse:
        try:
            return self.responses[url]
        except KeyError as exc:
            raise AssertionError(f"Unexpected URL requested in test: {url}") from exc


class JobcarbonIntegrationTests(unittest.TestCase):
    def test_jsonld_primary_path_returns_high_confidence(self) -> None:
        target_url = "https://jobs.lever.co/skio/bbdd5a7b-652a-43ad-b92e-58f4e970c694"
        session = FakeSession(
            {
                target_url: FakeResponse(text=load_text("lever_job_page.html")),
            }
        )

        result = jobcarbon.analyze_url(target_url, session=session, today=jobcarbon.date(2024, 3, 1))

        self.assertEqual(result["ats"], "lever")
        self.assertEqual(result["estimated_posted"], "2021-10-21")
        self.assertEqual(result["confidence"], "high")
        self.assertEqual(result["method"], "jsonld.jobposting.datePosted")

    def test_greenhouse_fallback_uses_first_published(self) -> None:
        target_url = "https://job-boards.greenhouse.io/applytogreenspark/jobs/4169702004"
        session = FakeSession(
            {
                target_url: FakeResponse(text=load_text("no_jsonld_page.html")),
                "https://boards-api.greenhouse.io/v1/boards/applytogreenspark/jobs/4169702004": FakeResponse(
                    json_data=load_json("greenhouse_job_api.json")
                ),
                "https://web.archive.org/cdx/search/cdx?url=https://job-boards.greenhouse.io/applytogreenspark/jobs/4169702004&limit=1&output=json&fl=timestamp,original&filter=statuscode:200&sort=ascending": FakeResponse(
                    json_data=load_json("wayback_first_snapshot.json")
                ),
            }
        )

        result = jobcarbon.analyze_url(target_url, session=session, today=jobcarbon.date(2024, 3, 1))

        self.assertEqual(result["estimated_posted"], "2021-11-03")
        self.assertEqual(result["confidence"], "high")
        self.assertEqual(result["method"], "greenhouse.api.first_published")
        evidence_fields = [item["field"] for item in result["evidence"]]
        self.assertIn("first_published", evidence_fields)
        self.assertIn("updated_at", evidence_fields)

    def test_ashby_fallback_uses_published_at(self) -> None:
        target_url = "https://jobs.ashbyhq.com/glimpse/767a3a59-53d6-4306-afae-6b05a265ba82"
        session = FakeSession(
            {
                target_url: FakeResponse(text=load_text("no_jsonld_page.html")),
                "https://api.ashbyhq.com/posting-api/job-board/glimpse": FakeResponse(
                    json_data=load_json("ashby_job_board_api.json")
                ),
                "https://web.archive.org/cdx/search/cdx?url=https://jobs.ashbyhq.com/glimpse/767a3a59-53d6-4306-afae-6b05a265ba82&limit=1&output=json&fl=timestamp,original&filter=statuscode:200&sort=ascending": FakeResponse(
                    json_data=load_json("wayback_first_snapshot.json")
                ),
            }
        )

        result = jobcarbon.analyze_url(target_url, session=session, today=jobcarbon.date(2026, 3, 1))

        self.assertEqual(result["estimated_posted"], "2026-02-19")
        self.assertEqual(result["confidence"], "high")
        self.assertEqual(result["method"], "ashby.api.publishedAt")

    def test_wayback_ceiling_is_used_last(self) -> None:
        target_url = "https://example.com/jobs/123"
        session = FakeSession(
            {
                target_url: FakeResponse(text=load_text("no_jsonld_page.html")),
                "https://web.archive.org/cdx/search/cdx?url=https://example.com/jobs/123&limit=1&output=json&fl=timestamp,original&filter=statuscode:200&sort=ascending": FakeResponse(
                    json_data=load_json("wayback_first_snapshot.json")
                ),
            }
        )

        result = jobcarbon.analyze_url(target_url, session=session, today=jobcarbon.date(2024, 3, 1))

        self.assertEqual(result["ats"], "unknown")
        self.assertEqual(result["estimated_posted"], "2021-04-05")
        self.assertEqual(result["confidence"], "low")
        self.assertEqual(result["method"], "wayback.first_snapshot_ceiling")

    def test_greenhouse_html_fallback_uses_embedded_published_at(self) -> None:
        target_url = "https://job-boards.greenhouse.io/speechify/jobs/5058944004"
        session = FakeSession(
            {
                target_url: FakeResponse(text=load_text("greenhouse_board_page.html")),
                "https://boards-api.greenhouse.io/v1/boards/speechify/jobs/5058944004": FakeResponse(
                    status_code=404
                ),
                "https://web.archive.org/cdx/search/cdx?url=https://job-boards.greenhouse.io/speechify/jobs/5058944004&limit=1&output=json&fl=timestamp,original&filter=statuscode:200&sort=ascending": FakeResponse(
                    json_data=load_json("wayback_first_snapshot.json")
                ),
            }
        )

        result = jobcarbon.analyze_url(target_url, session=session, today=jobcarbon.date(2026, 4, 14))

        self.assertEqual(result["estimated_posted"], "2024-01-24")
        self.assertEqual(result["confidence"], "high")
        self.assertEqual(result["method"], "greenhouse.html.published_at")
        evidence_sources = [item["source"] for item in result["evidence"]]
        self.assertIn("greenhouse.api", evidence_sources)
        self.assertIn("greenhouse.html", evidence_sources)

    def test_unknown_page_returns_structured_unknown_result(self) -> None:
        target_url = "https://example.com/jobs/456"
        session = FakeSession(
            {
                target_url: FakeResponse(text=load_text("no_jsonld_page.html")),
                "https://web.archive.org/cdx/search/cdx?url=https://example.com/jobs/456&limit=1&output=json&fl=timestamp,original&filter=statuscode:200&sort=ascending": FakeResponse(
                    json_data=[["timestamp", "original"]]
                ),
            }
        )

        result = jobcarbon.analyze_url(target_url, session=session, today=jobcarbon.date(2024, 3, 1))

        self.assertIsNone(result["estimated_posted"])
        self.assertEqual(result["confidence"], "unknown")
        self.assertEqual(result["method"], "unknown")


if __name__ == "__main__":
    unittest.main()
