from __future__ import annotations

import argparse
import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

import jobcarbon


JSON_HEADERS = {
    "Content-Type": "application/json; charset=utf-8",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Cache-Control": "no-store",
}


def json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, indent=2).encode("utf-8")


def parse_json_body(body: bytes) -> dict[str, Any]:
    if not body:
        return {}
    return json.loads(body.decode("utf-8"))


def error_payload(code: str, message: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message}}


def handle_api_request(
    *,
    method: str,
    path: str,
    query_string: str = "",
    body: bytes = b"",
    analyzer: Callable[[str], dict[str, Any]] = jobcarbon.analyze_url,
) -> tuple[int, dict[str, str], bytes]:
    if method == "OPTIONS":
        return HTTPStatus.NO_CONTENT, dict(JSON_HEADERS), b""

    if method == "GET" and path == "/healthz":
        return (
            HTTPStatus.OK,
            dict(JSON_HEADERS),
            json_bytes({"ok": True, "service": "jobcarbon-api"}),
        )

    if path != "/api/v1/estimate":
        return (
            HTTPStatus.NOT_FOUND,
            dict(JSON_HEADERS),
            json_bytes(error_payload("not_found", "Route not found.")),
        )

    if method == "GET":
        params = parse_qs(query_string)
        url = params.get("url", [None])[0]
    elif method == "POST":
        try:
            payload = parse_json_body(body)
        except json.JSONDecodeError:
            return (
                HTTPStatus.BAD_REQUEST,
                dict(JSON_HEADERS),
                json_bytes(error_payload("invalid_json", "Request body must be valid JSON.")),
            )
        url = payload.get("url")
    else:
        return (
            HTTPStatus.METHOD_NOT_ALLOWED,
            dict(JSON_HEADERS),
            json_bytes(error_payload("method_not_allowed", "Use GET, POST, or OPTIONS.")),
        )

    if not isinstance(url, str) or not url.strip():
        return (
            HTTPStatus.BAD_REQUEST,
            dict(JSON_HEADERS),
            json_bytes(error_payload("missing_url", "A non-empty 'url' value is required.")),
        )

    try:
        result = analyzer(url.strip())
    except jobcarbon.InvalidURLError as exc:
        return (
            HTTPStatus.BAD_REQUEST,
            dict(JSON_HEADERS),
            json_bytes(error_payload("invalid_url", str(exc))),
        )
    except jobcarbon.PageFetchError as exc:
        return (
            HTTPStatus.BAD_GATEWAY,
            dict(JSON_HEADERS),
            json_bytes(error_payload("upstream_fetch_failed", str(exc))),
        )
    except Exception as exc:  # pragma: no cover - defensive HTTP guard
        return (
            HTTPStatus.INTERNAL_SERVER_ERROR,
            dict(JSON_HEADERS),
            json_bytes(error_payload("internal_error", f"Unexpected error: {exc}")),
        )

    return HTTPStatus.OK, dict(JSON_HEADERS), json_bytes(result)


class JobcarbonAPIHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self) -> None:  # noqa: N802
        self._handle()

    def do_GET(self) -> None:  # noqa: N802
        self._handle()

    def do_POST(self) -> None:  # noqa: N802
        self._handle()

    def _handle(self) -> None:
        parsed = urlparse(self.path)
        body = b""
        if self.command == "POST":
            content_length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_length)

        status, headers, payload = handle_api_request(
            method=self.command,
            path=parsed.path,
            query_string=parsed.query,
            body=body,
        )

        self.send_response(status)
        for name, value in headers.items():
            self.send_header(name, value)
        self.end_headers()
        if payload:
            self.wfile.write(payload)

    def log_message(self, format: str, *args: Any) -> None:
        return


def default_host() -> str:
    return "0.0.0.0" if os.environ.get("PORT") else "127.0.0.1"


def default_port() -> int:
    return int(os.environ.get("PORT", "8000"))


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jobcarbon-api",
        description="Serve the jobcarbon detector over HTTP.",
    )
    parser.add_argument("--host", default=default_host(), help="Host interface to bind")
    parser.add_argument("--port", type=int, default=default_port(), help="Port to bind")
    return parser


def main() -> None:
    args = build_argument_parser().parse_args()
    server = ThreadingHTTPServer((args.host, args.port), JobcarbonAPIHandler)
    print(f"jobcarbon-api listening on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
