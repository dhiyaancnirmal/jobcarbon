import json
import os
import tempfile
import unittest
from http.cookies import SimpleCookie
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
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "jobcarbon-test.db")
        self.env_patch = mock.patch.dict(
            os.environ,
            {
                "JOBCARBON_DB_PATH": self.db_path,
                "JOBCARBON_ALLOWED_ORIGINS": "http://localhost:3000,https://howoldisthisjob.com,https://www.howoldisthisjob.com",
            },
            clear=False,
        )
        self.env_patch.start()
        jobcarbon_api._DB_INITIALIZED_PATHS.clear()

    def tearDown(self) -> None:
        self.env_patch.stop()
        self.temp_dir.cleanup()
        jobcarbon_api._DB_INITIALIZED_PATHS.clear()

    @staticmethod
    def _origin_headers(origin: str = "http://localhost:3000") -> dict[str, str]:
        return {"Origin": origin}

    @staticmethod
    def _extract_session_cookie(set_cookie_header: str) -> str:
        jar = SimpleCookie()
        jar.load(set_cookie_header)
        morsel = jar.get("jobcarbon_session")
        if morsel is None:
            raise AssertionError("Session cookie not set")
        return morsel.value

    def test_healthz(self) -> None:
        status, headers, body = jobcarbon_api.handle_api_request(
            method="GET",
            path="/healthz",
            request_headers=self._origin_headers(),
        )

        self.assertEqual(status, 200)
        self.assertEqual(headers["Access-Control-Allow-Origin"], "http://localhost:3000")
        self.assertEqual(headers["Access-Control-Allow-Credentials"], "true")
        self.assertEqual(json.loads(body), {"ok": True, "service": "jobcarbon-api"})

    def test_disallowed_origin_is_forbidden(self) -> None:
        status, _, body = jobcarbon_api.handle_api_request(
            method="GET",
            path="/healthz",
            request_headers=self._origin_headers("https://evil.example"),
        )

        self.assertEqual(status, 403)
        self.assertEqual(json.loads(body)["error"]["code"], "cors_origin_not_allowed")

    def test_estimate_get_success(self) -> None:
        status, _, body = jobcarbon_api.handle_api_request(
            method="GET",
            path="/api/v1/estimate",
            query_string="url=https%3A%2F%2Fjobs.lever.co%2Facme%2F123",
            analyzer=lambda url: sample_result(url, "lever"),
            request_headers=self._origin_headers(),
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
            request_headers=self._origin_headers(),
        )

        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["platform"], "greenhouse")

    def test_missing_url_is_bad_request(self) -> None:
        status, _, body = jobcarbon_api.handle_api_request(
            method="POST",
            path="/api/v1/estimate",
            body=b"{}",
            request_headers=self._origin_headers(),
        )

        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body)["error"]["code"], "missing_url")

    def test_invalid_json_is_bad_request(self) -> None:
        status, _, body = jobcarbon_api.handle_api_request(
            method="POST",
            path="/api/v1/estimate",
            body=b"{bad json",
            request_headers=self._origin_headers(),
        )

        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body)["error"]["code"], "invalid_json")

    def test_invalid_url_maps_to_bad_request(self) -> None:
        status, _, body = jobcarbon_api.handle_api_request(
            method="GET",
            path="/api/v1/estimate",
            query_string="url=notaurl",
            analyzer=lambda url: (_ for _ in ()).throw(jobcarbon.InvalidURLError("Invalid URL: notaurl")),
            request_headers=self._origin_headers(),
        )

        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body)["error"]["code"], "invalid_url")

    def test_page_fetch_error_maps_to_bad_gateway(self) -> None:
        status, _, body = jobcarbon_api.handle_api_request(
            method="GET",
            path="/api/v1/estimate",
            query_string="url=https%3A%2F%2Fexample.com%2Fjob",
            analyzer=lambda url: (_ for _ in ()).throw(jobcarbon.PageFetchError("Unable to fetch job page")),
            request_headers=self._origin_headers(),
        )

        self.assertEqual(status, 502)
        self.assertEqual(json.loads(body)["error"]["code"], "upstream_fetch_failed")

    def test_platforms_endpoint_returns_capability_matrix(self) -> None:
        status, headers, body = jobcarbon_api.handle_api_request(
            method="GET",
            path="/api/v1/platforms",
            request_headers=self._origin_headers(),
        )

        self.assertEqual(status, 200)
        self.assertEqual(headers["Access-Control-Allow-Origin"], "http://localhost:3000")
        payload = json.loads(body)
        platforms = {item["platform"]: item for item in payload["platforms"]}
        self.assertIn("workable", platforms)
        self.assertIn("lever", platforms)
        self.assertIn("indeed", platforms)
        self.assertIn("gem", platforms)
        self.assertIn("recruitee", platforms)
        self.assertIn("custom_backend", platforms)
        self.assertEqual(platforms["workable"]["integration"], "direct")
        self.assertEqual(platforms["gem"]["integration"], "direct")
        self.assertEqual(platforms["recruitee"]["integration"], "direct")
        self.assertEqual(platforms["custom_backend"]["integration"], "direct")
        self.assertEqual(platforms["indeed"]["integration"], "blocked")
        summary = payload["summary"]
        self.assertEqual(summary["supported"], summary["direct"] + summary["generic"])
        self.assertGreaterEqual(summary["direct"], 20)

    def test_platforms_endpoint_rejects_post(self) -> None:
        status, _, body = jobcarbon_api.handle_api_request(
            method="POST",
            path="/api/v1/platforms",
            body=b"{}",
            request_headers=self._origin_headers(),
        )

        self.assertEqual(status, 405)
        self.assertEqual(json.loads(body)["error"]["code"], "method_not_allowed")

    def test_history_get_without_cookie_returns_empty(self) -> None:
        status, _, body = jobcarbon_api.handle_api_request(
            method="GET",
            path="/api/v1/history",
            request_headers=self._origin_headers(),
        )

        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"history": []})

    def test_history_post_sets_cookie_and_persists(self) -> None:
        status, headers, body = jobcarbon_api.handle_api_request(
            method="POST",
            path="/api/v1/history",
            body=json.dumps(
                {
                    "url": "https://jobs.lever.co/acme/123",
                    "result": sample_result("https://jobs.lever.co/acme/123"),
                }
            ).encode("utf-8"),
            request_headers=self._origin_headers(),
        )

        self.assertEqual(status, 201)
        self.assertIn("Set-Cookie", headers)
        cookie_value = self._extract_session_cookie(headers["Set-Cookie"])

        get_status, _, get_body = jobcarbon_api.handle_api_request(
            method="GET",
            path="/api/v1/history",
            request_headers={
                **self._origin_headers(),
                "Cookie": f"jobcarbon_session={cookie_value}",
            },
        )

        self.assertEqual(get_status, 200)
        payload = json.loads(get_body)
        self.assertEqual(len(payload["history"]), 1)
        self.assertEqual(payload["history"][0]["url"], "https://jobs.lever.co/acme/123")
        self.assertEqual(payload["history"][0]["result"]["platform"], "lever")
        self.assertEqual(json.loads(body)["item"]["id"], payload["history"][0]["id"])

    def test_history_delete_item_is_idempotent_and_scoped(self) -> None:
        status, headers, body = jobcarbon_api.handle_api_request(
            method="POST",
            path="/api/v1/history",
            body=json.dumps(
                {
                    "url": "https://jobs.lever.co/acme/123",
                    "result": sample_result("https://jobs.lever.co/acme/123"),
                }
            ).encode("utf-8"),
            request_headers=self._origin_headers(),
        )
        self.assertEqual(status, 201)
        cookie_value = self._extract_session_cookie(headers["Set-Cookie"])
        item_id = json.loads(body)["item"]["id"]

        delete_status, _, delete_body = jobcarbon_api.handle_api_request(
            method="DELETE",
            path=f"/api/v1/history/{item_id}",
            request_headers={
                **self._origin_headers(),
                "Cookie": f"jobcarbon_session={cookie_value}",
            },
        )
        self.assertEqual(delete_status, 204)
        self.assertEqual(delete_body, b"")

        delete_again_status, _, _ = jobcarbon_api.handle_api_request(
            method="DELETE",
            path=f"/api/v1/history/{item_id}",
            request_headers={
                **self._origin_headers(),
                "Cookie": f"jobcarbon_session={cookie_value}",
            },
        )
        self.assertEqual(delete_again_status, 204)

        get_status, _, get_body = jobcarbon_api.handle_api_request(
            method="GET",
            path="/api/v1/history",
            request_headers={
                **self._origin_headers(),
                "Cookie": f"jobcarbon_session={cookie_value}",
            },
        )
        self.assertEqual(get_status, 200)
        self.assertEqual(json.loads(get_body)["history"], [])

    def test_history_clear_all_only_affects_current_session(self) -> None:
        # Session A
        status_a, headers_a, _ = jobcarbon_api.handle_api_request(
            method="POST",
            path="/api/v1/history",
            body=json.dumps(
                {
                    "url": "https://jobs.lever.co/acme/a",
                    "result": sample_result("https://jobs.lever.co/acme/a"),
                }
            ).encode("utf-8"),
            request_headers=self._origin_headers(),
        )
        self.assertEqual(status_a, 201)
        cookie_a = self._extract_session_cookie(headers_a["Set-Cookie"])

        # Session B
        status_b, headers_b, _ = jobcarbon_api.handle_api_request(
            method="POST",
            path="/api/v1/history",
            body=json.dumps(
                {
                    "url": "https://jobs.lever.co/acme/b",
                    "result": sample_result("https://jobs.lever.co/acme/b"),
                }
            ).encode("utf-8"),
            request_headers=self._origin_headers(),
        )
        self.assertEqual(status_b, 201)
        cookie_b = self._extract_session_cookie(headers_b["Set-Cookie"])

        clear_status, _, _ = jobcarbon_api.handle_api_request(
            method="DELETE",
            path="/api/v1/history",
            request_headers={
                **self._origin_headers(),
                "Cookie": f"jobcarbon_session={cookie_a}",
            },
        )
        self.assertEqual(clear_status, 204)

        get_a_status, _, get_a_body = jobcarbon_api.handle_api_request(
            method="GET",
            path="/api/v1/history",
            request_headers={
                **self._origin_headers(),
                "Cookie": f"jobcarbon_session={cookie_a}",
            },
        )
        get_b_status, _, get_b_body = jobcarbon_api.handle_api_request(
            method="GET",
            path="/api/v1/history",
            request_headers={
                **self._origin_headers(),
                "Cookie": f"jobcarbon_session={cookie_b}",
            },
        )

        self.assertEqual(get_a_status, 200)
        self.assertEqual(get_b_status, 200)
        self.assertEqual(json.loads(get_a_body)["history"], [])
        self.assertEqual(len(json.loads(get_b_body)["history"]), 1)
        self.assertEqual(json.loads(get_b_body)["history"][0]["url"], "https://jobs.lever.co/acme/b")

    def test_history_validates_payload(self) -> None:
        invalid_json_status, _, invalid_json_body = jobcarbon_api.handle_api_request(
            method="POST",
            path="/api/v1/history",
            body=b"{bad json",
            request_headers=self._origin_headers(),
        )
        self.assertEqual(invalid_json_status, 400)
        self.assertEqual(json.loads(invalid_json_body)["error"]["code"], "invalid_json")

        missing_url_status, _, missing_url_body = jobcarbon_api.handle_api_request(
            method="POST",
            path="/api/v1/history",
            body=json.dumps({"result": sample_result("https://jobs.lever.co/acme")}).encode("utf-8"),
            request_headers=self._origin_headers(),
        )
        self.assertEqual(missing_url_status, 400)
        self.assertEqual(json.loads(missing_url_body)["error"]["code"], "missing_url")

        missing_result_status, _, missing_result_body = jobcarbon_api.handle_api_request(
            method="POST",
            path="/api/v1/history",
            body=json.dumps({"url": "https://jobs.lever.co/acme"}).encode("utf-8"),
            request_headers=self._origin_headers(),
        )
        self.assertEqual(missing_result_status, 400)
        self.assertEqual(json.loads(missing_result_body)["error"]["code"], "missing_result")

    def test_options_returns_cors_headers(self) -> None:
        status, headers, body = jobcarbon_api.handle_api_request(
            method="OPTIONS",
            path="/api/v1/history",
            request_headers=self._origin_headers(),
        )

        self.assertEqual(status, 204)
        self.assertEqual(headers["Access-Control-Allow-Methods"], "GET, POST, DELETE, OPTIONS")
        self.assertEqual(headers["Access-Control-Allow-Credentials"], "true")
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
