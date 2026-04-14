import json
import os
import unittest
from unittest import mock

import jobcarbon
import jobcarbon_api


class JobcarbonAPITests(unittest.TestCase):
    def test_healthz(self) -> None:
        status, headers, body = jobcarbon_api.handle_api_request(
            method="GET",
            path="/healthz",
        )

        self.assertEqual(status, 200)
        self.assertEqual(headers["Access-Control-Allow-Origin"], "*")
        self.assertEqual(json.loads(body), {"ok": True, "service": "jobcarbon-api"})

    def test_estimate_get_success(self) -> None:
        def analyzer(url: str) -> dict:
            return {
                "url": url,
                "ats": "lever",
                "estimated_posted": "2024-01-01",
                "confidence": "high",
                "method": "jsonld.jobposting.datePosted",
                "age_days": 10,
                "evidence": [],
            }

        status, _, body = jobcarbon_api.handle_api_request(
            method="GET",
            path="/api/v1/estimate",
            query_string="url=https%3A%2F%2Fjobs.lever.co%2Facme%2F123",
            analyzer=analyzer,
        )

        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["ats"], "lever")

    def test_estimate_post_success(self) -> None:
        def analyzer(url: str) -> dict:
            return {
                "url": url,
                "ats": "greenhouse",
                "estimated_posted": "2024-02-02",
                "confidence": "high",
                "method": "greenhouse.api.first_published",
                "age_days": 5,
                "evidence": [],
            }

        status, _, body = jobcarbon_api.handle_api_request(
            method="POST",
            path="/api/v1/estimate",
            body=b'{"url": "https://job-boards.greenhouse.io/acme/jobs/123"}',
            analyzer=analyzer,
        )

        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["method"], "greenhouse.api.first_published")

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
