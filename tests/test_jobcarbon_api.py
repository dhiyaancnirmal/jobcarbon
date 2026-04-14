import json
import os
import unittest
from unittest import mock

import jobcarbon
import jobcarbon_api


def sample_result(url: str, platform: str = "lever") -> dict:
    return {
        "url": url,
        "normalized_url": url,
        "platform": platform,
        "status": "success",
        "title": "Example Job",
        "company": "Example Co",
        "location": "Remote",
        "employment_type": "Full-time",
        "likely_posted_date": "2024-01-01",
        "likely_age_days": 10,
        "confidence": "high",
        "reposted_likely": False,
        "summary": "Oldest credible posted date is 2024-01-01 from jsonld.jobposting.datePosted.",
        "chosen_source": {
            "date": "2024-01-01",
            "source": "jsonld.jobposting",
            "field": "datePosted",
            "kind": "posted",
            "reliability": "high",
        },
        "all_dates": [],
        "hidden_insights": {},
        "warnings": [],
    }


class JobcarbonAPITests(unittest.TestCase):
    def test_healthz(self) -> None:
        status, headers, body = jobcarbon_api.handle_api_request(method="GET", path="/healthz")

        self.assertEqual(status, 200)
        self.assertEqual(headers["Access-Control-Allow-Origin"], "*")
        self.assertEqual(json.loads(body), {"ok": True, "service": "jobcarbon-api"})

    def test_estimate_get_success(self) -> None:
        status, _, body = jobcarbon_api.handle_api_request(
            method="GET",
            path="/api/v1/estimate",
            query_string="url=https%3A%2F%2Fjobs.lever.co%2Facme%2F123",
            analyzer=lambda url: sample_result(url, "lever"),
        )

        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["platform"], "lever")
        self.assertEqual(payload["chosen_source"]["field"], "datePosted")

    def test_estimate_post_success(self) -> None:
        status, _, body = jobcarbon_api.handle_api_request(
            method="POST",
            path="/api/v1/estimate",
            body=b'{"url": "https://job-boards.greenhouse.io/acme/jobs/123"}',
            analyzer=lambda url: sample_result(url, "greenhouse"),
        )

        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["platform"], "greenhouse")

    def test_missing_url_is_bad_request(self) -> None:
        status, _, body = jobcarbon_api.handle_api_request(
            method="POST",
            path="/api/v1/estimate",
            body=b"{}",
        )

        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body)["error"]["code"], "missing_url")

    def test_invalid_json_is_bad_request(self) -> None:
        status, _, body = jobcarbon_api.handle_api_request(
            method="POST",
            path="/api/v1/estimate",
            body=b"{bad json",
        )

        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body)["error"]["code"], "invalid_json")

    def test_invalid_url_maps_to_bad_request(self) -> None:
        status, _, body = jobcarbon_api.handle_api_request(
            method="GET",
            path="/api/v1/estimate",
            query_string="url=notaurl",
            analyzer=lambda url: (_ for _ in ()).throw(jobcarbon.InvalidURLError("Invalid URL: notaurl")),
        )

        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body)["error"]["code"], "invalid_url")

    def test_page_fetch_error_maps_to_bad_gateway(self) -> None:
        status, _, body = jobcarbon_api.handle_api_request(
            method="GET",
            path="/api/v1/estimate",
            query_string="url=https%3A%2F%2Fexample.com%2Fjob",
            analyzer=lambda url: (_ for _ in ()).throw(jobcarbon.PageFetchError("Unable to fetch job page")),
        )

        self.assertEqual(status, 502)
        self.assertEqual(json.loads(body)["error"]["code"], "upstream_fetch_failed")

    def test_platforms_endpoint_returns_capability_matrix(self) -> None:
        status, headers, body = jobcarbon_api.handle_api_request(
            method="GET",
            path="/api/v1/platforms",
        )

        self.assertEqual(status, 200)
        self.assertEqual(headers["Access-Control-Allow-Origin"], "*")
        payload = json.loads(body)
        platforms = {item["platform"]: item for item in payload["platforms"]}
        self.assertIn("workable", platforms)
        self.assertIn("lever", platforms)
        self.assertIn("indeed", platforms)
        self.assertEqual(platforms["workable"]["integration"], "direct")
        self.assertEqual(platforms["indeed"]["integration"], "blocked")
        summary = payload["summary"]
        self.assertEqual(summary["supported"], summary["direct"] + summary["generic"])
        self.assertGreaterEqual(summary["direct"], 13)

    def test_platforms_endpoint_rejects_post(self) -> None:
        status, _, body = jobcarbon_api.handle_api_request(
            method="POST",
            path="/api/v1/platforms",
            body=b"{}",
        )

        self.assertEqual(status, 405)
        self.assertEqual(json.loads(body)["error"]["code"], "method_not_allowed")

    def test_options_returns_cors_headers(self) -> None:
        status, headers, body = jobcarbon_api.handle_api_request(
            method="OPTIONS",
            path="/api/v1/estimate",
        )

        self.assertEqual(status, 204)
        self.assertEqual(headers["Access-Control-Allow-Methods"], "GET, POST, OPTIONS")
        self.assertEqual(body, b"")

    def test_default_host_uses_railway_binding_when_port_is_present(self) -> None:
        with mock.patch.dict(os.environ, {"PORT": "8080"}, clear=False):
            self.assertEqual(jobcarbon_api.default_host(), "0.0.0.0")
            self.assertEqual(jobcarbon_api.default_port(), 8080)

    def test_default_host_uses_local_defaults_without_port(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(jobcarbon_api.default_host(), "127.0.0.1")
            self.assertEqual(jobcarbon_api.default_port(), 8000)


if __name__ == "__main__":
    unittest.main()
