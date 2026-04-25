import json
import os
import tempfile
import threading
import time
import unittest
from http.cookies import SimpleCookie
from unittest import mock

import howoldisthisjob
import howoldisthisjob_api


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
    extension_origin = "chrome-extension://efdbbcgmlpnildldcnalbdfhpndhmmcl"
    renamed_extension_origin = "chrome-extension://nhaadlmaijnkebibldhidgdgghnehfea"

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "howoldisthisjob-test.db")
        self.env_patch = mock.patch.dict(
            os.environ,
            {
                "HOWOLDISTHISJOB_DB_PATH": self.db_path,
                "HOWOLDISTHISJOB_ALLOWED_ORIGINS": "http://localhost:3000,https://howoldisthisjob.com,https://www.howoldisthisjob.com",
            },
            clear=False,
        )
        self.env_patch.start()
        howoldisthisjob_api._DB_INITIALIZED_PATHS.clear()

    def tearDown(self) -> None:
        self.env_patch.stop()
        self.temp_dir.cleanup()
        howoldisthisjob_api._DB_INITIALIZED_PATHS.clear()

    @staticmethod
    def _origin_headers(origin: str = "http://localhost:3000") -> dict[str, str]:
        return {"Origin": origin}

    @staticmethod
    def _extract_session_cookie(set_cookie_header: str) -> str:
        jar = SimpleCookie()
        jar.load(set_cookie_header)
        morsel = jar.get("howoldisthisjob_session")
        if morsel is None:
            raise AssertionError("Session cookie not set")
        return morsel.value

    def test_healthz(self) -> None:
        status, headers, body = howoldisthisjob_api.handle_api_request(
            method="GET",
            path="/healthz",
            request_headers=self._origin_headers(),
        )

        self.assertEqual(status, 200)
        self.assertEqual(
            headers["Access-Control-Allow-Origin"], "http://localhost:3000"
        )
        self.assertEqual(headers["Access-Control-Allow-Credentials"], "true")
        self.assertEqual(json.loads(body), {"ok": True, "service": "howoldisthisjob-api"})

    def test_disallowed_origin_is_forbidden(self) -> None:
        status, _, body = howoldisthisjob_api.handle_api_request(
            method="GET",
            path="/healthz",
            request_headers=self._origin_headers("https://evil.example"),
        )

        self.assertEqual(status, 403)
        self.assertEqual(json.loads(body)["error"]["code"], "cors_origin_not_allowed")

    def test_allowed_extension_origin_is_accepted(self) -> None:
        status, headers, body = howoldisthisjob_api.handle_api_request(
            method="GET",
            path="/healthz",
            request_headers=self._origin_headers(self.extension_origin),
        )

        self.assertEqual(status, 200)
        self.assertEqual(headers["Access-Control-Allow-Origin"], self.extension_origin)
        self.assertEqual(headers["Access-Control-Allow-Credentials"], "true")
        self.assertEqual(json.loads(body), {"ok": True, "service": "howoldisthisjob-api"})

    def test_renamed_extension_origin_is_accepted(self) -> None:
        status, headers, body = howoldisthisjob_api.handle_api_request(
            method="GET",
            path="/healthz",
            request_headers=self._origin_headers(self.renamed_extension_origin),
        )

        self.assertEqual(status, 200)
        self.assertEqual(
            headers["Access-Control-Allow-Origin"], self.renamed_extension_origin
        )
        self.assertEqual(headers["Access-Control-Allow-Credentials"], "true")
        self.assertEqual(json.loads(body), {"ok": True, "service": "howoldisthisjob-api"})

    def test_extension_origin_env_accepts_raw_extension_id(self) -> None:
        raw_extension_id = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        with mock.patch.dict(
            os.environ,
            {"HOWOLDISTHISJOB_ALLOWED_EXTENSION_ORIGINS": raw_extension_id},
            clear=False,
        ):
            status, headers, body = howoldisthisjob_api.handle_api_request(
                method="GET",
                path="/healthz",
                request_headers=self._origin_headers(
                    f"chrome-extension://{raw_extension_id}"
                ),
            )

        self.assertEqual(status, 200)
        self.assertEqual(
            headers["Access-Control-Allow-Origin"],
            f"chrome-extension://{raw_extension_id}",
        )
        self.assertEqual(json.loads(body), {"ok": True, "service": "howoldisthisjob-api"})

    def test_estimate_get_success(self) -> None:
        status, _, body = howoldisthisjob_api.handle_api_request(
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
        status, _, body = howoldisthisjob_api.handle_api_request(
            method="POST",
            path="/api/v1/estimate",
            body=b'{"url": "https://job-boards.greenhouse.io/acme/jobs/123"}',
            analyzer=lambda url: sample_result(url, "greenhouse"),
            request_headers=self._origin_headers(),
        )

        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["platform"], "greenhouse")

    def test_batch_estimate_post_success(self) -> None:
        status, _, body = howoldisthisjob_api.handle_api_request(
            method="POST",
            path="/api/v1/batch-estimate",
            body=json.dumps(
                {
                    "urls": [
                        "https://jobs.lever.co/acme/123",
                        "https://job-boards.greenhouse.io/acme/jobs/456",
                    ]
                }
            ).encode("utf-8"),
            analyzer=lambda url: sample_result(
                url, "lever" if "lever" in url else "greenhouse"
            ),
            request_headers=self._origin_headers(),
        )

        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(len(payload["results"]), 2)
        self.assertTrue(payload["results"][0]["ok"])
        self.assertEqual(payload["results"][0]["result"]["platform"], "lever")
        self.assertEqual(payload["results"][1]["result"]["platform"], "greenhouse")

    def test_batch_estimate_returns_per_item_errors(self) -> None:
        def analyzer(url: str) -> dict:
            if "bad" in url:
                raise howoldisthisjob.InvalidURLError(f"Invalid URL: {url}")
            return sample_result(url, "lever")

        status, _, body = howoldisthisjob_api.handle_api_request(
            method="POST",
            path="/api/v1/batch-estimate",
            body=json.dumps(
                {
                    "urls": [
                        "https://jobs.lever.co/acme/123",
                        "https://bad.example/job",
                    ]
                }
            ).encode("utf-8"),
            analyzer=analyzer,
            request_headers=self._origin_headers(),
        )

        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertTrue(payload["results"][0]["ok"])
        self.assertFalse(payload["results"][1]["ok"])
        self.assertEqual(payload["results"][1]["error"]["code"], "invalid_url")

    def test_batch_estimate_uses_multiple_workers_and_preserves_input_order(self) -> None:
        thread_ids: set[int] = set()
        thread_lock = threading.Lock()
        delays = {
            "https://jobs.lever.co/acme/slow": 0.05,
            "https://jobs.lever.co/acme/fast": 0.01,
            "https://jobs.lever.co/acme/medium": 0.03,
        }

        def analyzer(url: str) -> dict:
            with thread_lock:
                thread_ids.add(threading.get_ident())
            time.sleep(delays[url])
            return sample_result(url, "lever")

        with mock.patch.dict(
            os.environ,
            {"HOWOLDISTHISJOB_BATCH_MAX_WORKERS": "4"},
            clear=False,
        ):
            status, _, body = howoldisthisjob_api.handle_api_request(
                method="POST",
                path="/api/v1/batch-estimate",
                body=json.dumps(
                    {
                        "urls": [
                            "https://jobs.lever.co/acme/slow",
                            "https://jobs.lever.co/acme/fast",
                            "https://jobs.lever.co/acme/medium",
                        ]
                    }
                ).encode("utf-8"),
                analyzer=analyzer,
                request_headers=self._origin_headers(),
            )

        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(
            [item["url"] for item in payload["results"]],
            [
                "https://jobs.lever.co/acme/slow",
                "https://jobs.lever.co/acme/fast",
                "https://jobs.lever.co/acme/medium",
            ],
        )
        self.assertGreater(len(thread_ids), 1)

    def test_batch_estimate_requires_non_empty_url_array(self) -> None:
        status, _, body = howoldisthisjob_api.handle_api_request(
            method="POST",
            path="/api/v1/batch-estimate",
            body=b'{"urls": []}',
            request_headers=self._origin_headers(),
        )

        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body)["error"]["code"], "missing_urls")

    def test_batch_estimate_rejects_get(self) -> None:
        status, _, body = howoldisthisjob_api.handle_api_request(
            method="GET",
            path="/api/v1/batch-estimate",
            request_headers=self._origin_headers(),
        )

        self.assertEqual(status, 405)
        self.assertEqual(json.loads(body)["error"]["code"], "method_not_allowed")

    def test_missing_url_is_bad_request(self) -> None:
        status, _, body = howoldisthisjob_api.handle_api_request(
            method="POST",
            path="/api/v1/estimate",
            body=b"{}",
            request_headers=self._origin_headers(),
        )

        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body)["error"]["code"], "missing_url")

    def test_invalid_json_is_bad_request(self) -> None:
        status, _, body = howoldisthisjob_api.handle_api_request(
            method="POST",
            path="/api/v1/estimate",
            body=b"{bad json",
            request_headers=self._origin_headers(),
        )

        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body)["error"]["code"], "invalid_json")

    def test_invalid_url_maps_to_bad_request(self) -> None:
        status, _, body = howoldisthisjob_api.handle_api_request(
            method="GET",
            path="/api/v1/estimate",
            query_string="url=notaurl",
            analyzer=lambda url: (_ for _ in ()).throw(
                howoldisthisjob.InvalidURLError("Invalid URL: notaurl")
            ),
            request_headers=self._origin_headers(),
        )

        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body)["error"]["code"], "invalid_url")

    def test_page_fetch_error_maps_to_bad_gateway(self) -> None:
        status, _, body = howoldisthisjob_api.handle_api_request(
            method="GET",
            path="/api/v1/estimate",
            query_string="url=https%3A%2F%2Fexample.com%2Fjob",
            analyzer=lambda url: (_ for _ in ()).throw(
                howoldisthisjob.PageFetchError("Unable to fetch job page")
            ),
            request_headers=self._origin_headers(),
        )

        self.assertEqual(status, 502)
        self.assertEqual(json.loads(body)["error"]["code"], "upstream_fetch_failed")

    def test_http_request_error_maps_to_bad_gateway_with_payload_code(self) -> None:
        status, _, body = howoldisthisjob_api.handle_api_request(
            method="GET",
            path="/api/v1/estimate",
            query_string="url=https%3A%2F%2Fexample.com%2Fjob",
            analyzer=lambda url: (_ for _ in ()).throw(
                howoldisthisjob.HTTPRequestError(
                    "Malformed JSON payload for url: https://example.com/api"
                )
            ),
            request_headers=self._origin_headers(),
        )

        self.assertEqual(status, 502)
        self.assertEqual(json.loads(body)["error"]["code"], "upstream_payload_error")

    def test_platforms_endpoint_returns_capability_matrix(self) -> None:
        status, headers, body = howoldisthisjob_api.handle_api_request(
            method="GET",
            path="/api/v1/platforms",
            request_headers=self._origin_headers(),
        )

        self.assertEqual(status, 200)
        self.assertEqual(
            headers["Access-Control-Allow-Origin"], "http://localhost:3000"
        )
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
        status, _, body = howoldisthisjob_api.handle_api_request(
            method="POST",
            path="/api/v1/platforms",
            body=b"{}",
            request_headers=self._origin_headers(),
        )

        self.assertEqual(status, 405)
        self.assertEqual(json.loads(body)["error"]["code"], "method_not_allowed")

    def test_history_get_without_cookie_returns_empty(self) -> None:
        status, _, body = howoldisthisjob_api.handle_api_request(
            method="GET",
            path="/api/v1/history",
            request_headers=self._origin_headers(),
        )

        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"history": []})

    def test_history_post_sets_cookie_and_persists(self) -> None:
        status, headers, body = howoldisthisjob_api.handle_api_request(
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

        get_status, _, get_body = howoldisthisjob_api.handle_api_request(
            method="GET",
            path="/api/v1/history",
            request_headers={
                **self._origin_headers(),
                "Cookie": f"howoldisthisjob_session={cookie_value}",
            },
        )

        self.assertEqual(get_status, 200)
        payload = json.loads(get_body)
        self.assertEqual(len(payload["history"]), 1)
        self.assertEqual(payload["history"][0]["url"], "https://jobs.lever.co/acme/123")
        self.assertEqual(payload["history"][0]["result"]["platform"], "lever")
        self.assertEqual(json.loads(body)["item"]["id"], payload["history"][0]["id"])

    def test_history_post_upserts_existing_url(self) -> None:
        first_status, first_headers, first_body = howoldisthisjob_api.handle_api_request(
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

        self.assertEqual(first_status, 201)
        cookie_value = self._extract_session_cookie(first_headers["Set-Cookie"])
        first_item = json.loads(first_body)["item"]

        second_status, _, second_body = howoldisthisjob_api.handle_api_request(
            method="POST",
            path="/api/v1/history",
            body=json.dumps(
                {
                    "url": "https://jobs.lever.co/acme/123",
                    "result": {
                        **sample_result("https://jobs.lever.co/acme/123"),
                        "summary": "Updated summary",
                    },
                }
            ).encode("utf-8"),
            request_headers={
                **self._origin_headers(),
                "Cookie": f"howoldisthisjob_session={cookie_value}",
            },
        )

        self.assertEqual(second_status, 201)
        second_item = json.loads(second_body)["item"]
        self.assertEqual(second_item["id"], first_item["id"])
        self.assertEqual(second_item["result"]["summary"], "Updated summary")

        get_status, _, get_body = howoldisthisjob_api.handle_api_request(
            method="GET",
            path="/api/v1/history",
            request_headers={
                **self._origin_headers(),
                "Cookie": f"howoldisthisjob_session={cookie_value}",
            },
        )

        self.assertEqual(get_status, 200)
        payload = json.loads(get_body)
        self.assertEqual(len(payload["history"]), 1)
        self.assertEqual(payload["history"][0]["id"], first_item["id"])
        self.assertEqual(payload["history"][0]["result"]["summary"], "Updated summary")

    def test_history_delete_item_is_idempotent_and_scoped(self) -> None:
        status, headers, body = howoldisthisjob_api.handle_api_request(
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

        delete_status, _, delete_body = howoldisthisjob_api.handle_api_request(
            method="DELETE",
            path=f"/api/v1/history/{item_id}",
            request_headers={
                **self._origin_headers(),
                "Cookie": f"howoldisthisjob_session={cookie_value}",
            },
        )
        self.assertEqual(delete_status, 204)
        self.assertEqual(delete_body, b"")

        delete_again_status, _, _ = howoldisthisjob_api.handle_api_request(
            method="DELETE",
            path=f"/api/v1/history/{item_id}",
            request_headers={
                **self._origin_headers(),
                "Cookie": f"howoldisthisjob_session={cookie_value}",
            },
        )
        self.assertEqual(delete_again_status, 204)

        get_status, _, get_body = howoldisthisjob_api.handle_api_request(
            method="GET",
            path="/api/v1/history",
            request_headers={
                **self._origin_headers(),
                "Cookie": f"howoldisthisjob_session={cookie_value}",
            },
        )
        self.assertEqual(get_status, 200)
        self.assertEqual(json.loads(get_body)["history"], [])

    def test_history_clear_all_only_affects_current_session(self) -> None:
        # Session A
        status_a, headers_a, _ = howoldisthisjob_api.handle_api_request(
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
        status_b, headers_b, _ = howoldisthisjob_api.handle_api_request(
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

        clear_status, _, _ = howoldisthisjob_api.handle_api_request(
            method="DELETE",
            path="/api/v1/history",
            request_headers={
                **self._origin_headers(),
                "Cookie": f"howoldisthisjob_session={cookie_a}",
            },
        )
        self.assertEqual(clear_status, 204)

        get_a_status, _, get_a_body = howoldisthisjob_api.handle_api_request(
            method="GET",
            path="/api/v1/history",
            request_headers={
                **self._origin_headers(),
                "Cookie": f"howoldisthisjob_session={cookie_a}",
            },
        )
        get_b_status, _, get_b_body = howoldisthisjob_api.handle_api_request(
            method="GET",
            path="/api/v1/history",
            request_headers={
                **self._origin_headers(),
                "Cookie": f"howoldisthisjob_session={cookie_b}",
            },
        )

        self.assertEqual(get_a_status, 200)
        self.assertEqual(get_b_status, 200)
        self.assertEqual(json.loads(get_a_body)["history"], [])
        self.assertEqual(len(json.loads(get_b_body)["history"]), 1)
        self.assertEqual(
            json.loads(get_b_body)["history"][0]["url"], "https://jobs.lever.co/acme/b"
        )

    def test_history_validates_payload(self) -> None:
        invalid_json_status, _, invalid_json_body = howoldisthisjob_api.handle_api_request(
            method="POST",
            path="/api/v1/history",
            body=b"{bad json",
            request_headers=self._origin_headers(),
        )
        self.assertEqual(invalid_json_status, 400)
        self.assertEqual(json.loads(invalid_json_body)["error"]["code"], "invalid_json")

        missing_url_status, _, missing_url_body = howoldisthisjob_api.handle_api_request(
            method="POST",
            path="/api/v1/history",
            body=json.dumps(
                {"result": sample_result("https://jobs.lever.co/acme")}
            ).encode("utf-8"),
            request_headers=self._origin_headers(),
        )
        self.assertEqual(missing_url_status, 400)
        self.assertEqual(json.loads(missing_url_body)["error"]["code"], "missing_url")

        missing_result_status, _, missing_result_body = (
            howoldisthisjob_api.handle_api_request(
                method="POST",
                path="/api/v1/history",
                body=json.dumps({"url": "https://jobs.lever.co/acme"}).encode("utf-8"),
                request_headers=self._origin_headers(),
            )
        )
        self.assertEqual(missing_result_status, 400)
        self.assertEqual(
            json.loads(missing_result_body)["error"]["code"], "missing_result"
        )

    def test_options_returns_cors_headers(self) -> None:
        status, headers, body = howoldisthisjob_api.handle_api_request(
            method="OPTIONS",
            path="/api/v1/history",
            request_headers=self._origin_headers(),
        )

        self.assertEqual(status, 204)
        self.assertEqual(
            headers["Access-Control-Allow-Methods"], "GET, POST, DELETE, OPTIONS"
        )
        self.assertEqual(headers["Access-Control-Allow-Credentials"], "true")
        self.assertEqual(body, b"")

    def test_default_host_uses_railway_binding_when_port_is_present(self) -> None:
        with mock.patch.dict(os.environ, {"PORT": "8080"}, clear=False):
            self.assertEqual(howoldisthisjob_api.default_host(), "0.0.0.0")
            self.assertEqual(howoldisthisjob_api.default_port(), 8080)

    def test_default_host_uses_local_defaults_without_port(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(howoldisthisjob_api.default_host(), "127.0.0.1")
            self.assertEqual(howoldisthisjob_api.default_port(), 8000)


class RunStreamEstimateTests(unittest.TestCase):
    @staticmethod
    def _collect(written: list[bytes]) -> list[dict]:
        joined = b"".join(written).decode("utf-8")
        return [
            json.loads(line)
            for line in joined.split("\n")
            if line.strip()
        ]

    def test_success_path_emits_scripted_stages_then_result(self) -> None:
        url = "https://jobs.lever.co/example/abc"
        result_payload = sample_result(url)
        written: list[bytes] = []

        def analyzer(passed_url: str) -> dict:
            self.assertEqual(passed_url, url)
            howoldisthisjob._emit_progress({"type": "platform", "platform": "lever"})
            howoldisthisjob._emit_progress(
                {"type": "stage", "label": "Page fetch", "status": "start"}
            )
            howoldisthisjob._emit_progress(
                {"type": "stage", "label": "Page fetch", "status": "ok"}
            )
            return result_payload

        howoldisthisjob_api.run_stream_estimate(url, written.append, analyzer=analyzer)

        events = self._collect(written)
        self.assertEqual(events[0], {"type": "platform", "platform": "lever"})
        self.assertEqual(
            events[1], {"type": "stage", "label": "Page fetch", "status": "start"}
        )
        self.assertEqual(
            events[2], {"type": "stage", "label": "Page fetch", "status": "ok"}
        )
        self.assertEqual(events[-1], {"type": "result", "result": result_payload})

    def test_invalid_url_error_is_mapped_to_error_event(self) -> None:
        written: list[bytes] = []

        def analyzer(_url: str) -> dict:
            raise howoldisthisjob.InvalidURLError("Invalid URL: bogus")

        howoldisthisjob_api.run_stream_estimate("bogus", written.append, analyzer=analyzer)

        events = self._collect(written)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "error")
        self.assertEqual(events[0]["code"], "invalid_url")
        self.assertIn("Invalid URL", events[0]["message"])

    def test_http_request_error_maps_to_upstream_payload_error(self) -> None:
        written: list[bytes] = []

        def analyzer(_url: str) -> dict:
            raise howoldisthisjob.HTTPRequestError("Malformed JSON from upstream")

        howoldisthisjob_api.run_stream_estimate(
            "https://jobs.lever.co/example/abc", written.append, analyzer=analyzer
        )

        events = self._collect(written)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "error")
        self.assertEqual(events[0]["code"], "upstream_payload_error")

    def test_page_fetch_error_maps_to_upstream_fetch_failed(self) -> None:
        written: list[bytes] = []

        def analyzer(_url: str) -> dict:
            raise howoldisthisjob.PageFetchError("Could not reach page")

        howoldisthisjob_api.run_stream_estimate(
            "https://jobs.lever.co/example/abc", written.append, analyzer=analyzer
        )

        events = self._collect(written)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "error")
        self.assertEqual(events[0]["code"], "upstream_fetch_failed")

    def test_emitter_is_reset_after_run(self) -> None:
        def analyzer(_url: str) -> dict:
            return sample_result("https://jobs.lever.co/example/abc")

        howoldisthisjob_api.run_stream_estimate(
            "https://jobs.lever.co/example/abc",
            lambda _b: None,
            analyzer=analyzer,
        )

        self.assertIsNone(howoldisthisjob._progress_emitter.get())

    def test_write_errors_do_not_propagate(self) -> None:
        def analyzer(_url: str) -> dict:
            howoldisthisjob._emit_progress(
                {"type": "stage", "label": "Page fetch", "status": "start"}
            )
            return sample_result("https://jobs.lever.co/example/abc")

        def failing_write(_data: bytes) -> None:
            raise BrokenPipeError("client disconnected")

        howoldisthisjob_api.run_stream_estimate(
            "https://jobs.lever.co/example/abc",
            failing_write,
            analyzer=analyzer,
        )


class StreamURLFromRequestTests(unittest.TestCase):
    def test_get_extracts_url_param(self) -> None:
        url, err = howoldisthisjob_api._stream_url_from_request(
            "GET", "url=https%3A%2F%2Fexample.com%2Fjob", b""
        )
        self.assertEqual(url, "https://example.com/job")
        self.assertIsNone(err)

    def test_missing_url_returns_error_payload(self) -> None:
        url, err = howoldisthisjob_api._stream_url_from_request("GET", "", b"")
        self.assertIsNone(url)
        self.assertEqual(err["error"]["code"], "missing_url")

    def test_post_parses_json_body(self) -> None:
        body = json.dumps({"url": "https://example.com/job"}).encode("utf-8")
        url, err = howoldisthisjob_api._stream_url_from_request("POST", "", body)
        self.assertEqual(url, "https://example.com/job")
        self.assertIsNone(err)

    def test_post_invalid_json_returns_error(self) -> None:
        url, err = howoldisthisjob_api._stream_url_from_request("POST", "", b"{not json")
        self.assertIsNone(url)
        self.assertEqual(err["error"]["code"], "invalid_json")

    def test_unsupported_method_returns_method_not_allowed(self) -> None:
        url, err = howoldisthisjob_api._stream_url_from_request("PUT", "", b"")
        self.assertIsNone(url)
        self.assertEqual(err["error"]["code"], "method_not_allowed")


if __name__ == "__main__":
    unittest.main()
