from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

import jobcarbon


DEFAULT_ALLOWED_ORIGINS = (
    "http://localhost:3000",
    "https://howoldisthisjob.com",
    "https://www.howoldisthisjob.com",
)
SESSION_COOKIE_NAME = "jobcarbon_session"
SESSION_MAX_AGE_SECONDS = 30 * 24 * 60 * 60

BASE_HEADERS = {
    "Content-Type": "application/json; charset=utf-8",
    "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Cache-Control": "no-store",
    "Vary": "Origin",
}

STREAM_PATH = "/api/v1/estimate/stream"

_DB_INIT_LOCK = threading.Lock()
_DB_INITIALIZED_PATHS: set[str] = set()


def json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, indent=2).encode("utf-8")


def parse_json_body(body: bytes) -> dict[str, Any]:
    if not body:
        return {}
    payload = json.loads(body.decode("utf-8"))
    if not isinstance(payload, dict):
        raise json.JSONDecodeError("JSON body must be an object", "", 0)
    return payload


def error_payload(code: str, message: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message}}


def _utcnow_iso() -> str:
    return (
        datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    )


def _get_header(headers: dict[str, str] | None, name: str) -> str | None:
    if not headers:
        return None
    wanted = name.lower()
    for key, value in headers.items():
        if key.lower() == wanted:
            return value
    return None


def _allowed_origins() -> set[str]:
    raw = os.environ.get("JOBCARBON_ALLOWED_ORIGINS")
    if not raw:
        return set(DEFAULT_ALLOWED_ORIGINS)
    return {entry.strip() for entry in raw.split(",") if entry.strip()}


def _build_headers(
    request_headers: dict[str, str] | None,
) -> tuple[dict[str, str], str | None, bool]:
    headers = dict(BASE_HEADERS)
    origin = _get_header(request_headers, "Origin")
    if not origin:
        return headers, None, False

    if origin not in _allowed_origins():
        return headers, origin, False

    headers["Access-Control-Allow-Origin"] = origin
    headers["Access-Control-Allow-Credentials"] = "true"
    return headers, origin, True


def _db_path() -> Path:
    configured = os.environ.get("JOBCARBON_DB_PATH", ".tmp/jobcarbon.db")
    return Path(configured)


def _db_connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    _ensure_db_initialized(path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _ensure_db_initialized(path: Path) -> None:
    path_key = str(path.resolve())
    with _DB_INIT_LOCK:
        if path_key in _DB_INITIALIZED_PATHS:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS anonymous_sessions (
                  id TEXT PRIMARY KEY,
                  cookie_token_hash TEXT UNIQUE NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS search_history (
                  id TEXT PRIMARY KEY,
                  session_id TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  url TEXT NOT NULL,
                  result_json TEXT NOT NULL,
                  FOREIGN KEY (session_id) REFERENCES anonymous_sessions(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_search_history_session_created_at
                ON search_history (session_id, created_at DESC)
                """
            )
            conn.commit()
            _DB_INITIALIZED_PATHS.add(path_key)
        finally:
            conn.close()


def _hash_cookie_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _parse_cookie_token(request_headers: dict[str, str] | None) -> str | None:
    raw_cookie = _get_header(request_headers, "Cookie")
    if not raw_cookie:
        return None
    jar = SimpleCookie()
    jar.load(raw_cookie)
    morsel = jar.get(SESSION_COOKIE_NAME)
    if morsel is None:
        return None
    value = morsel.value.strip()
    return value or None


def _build_session_cookie(token: str) -> str:
    cookie = SimpleCookie()
    cookie[SESSION_COOKIE_NAME] = token
    morsel = cookie[SESSION_COOKIE_NAME]
    morsel["httponly"] = True
    morsel["secure"] = True
    morsel["samesite"] = "None"
    morsel["path"] = "/"
    morsel["max-age"] = str(SESSION_MAX_AGE_SECONDS)
    cookie_domain = os.environ.get("JOBCARBON_COOKIE_DOMAIN", "").strip()
    if cookie_domain:
        morsel["domain"] = cookie_domain
    return cookie.output(header="").strip()


def _resolve_or_create_session(
    request_headers: dict[str, str] | None,
    *,
    create_if_missing: bool,
) -> tuple[str | None, str | None]:
    cookie_token = _parse_cookie_token(request_headers)
    if cookie_token:
        token_hash = _hash_cookie_token(cookie_token)
        with _db_connect() as conn:
            row = conn.execute(
                "SELECT id FROM anonymous_sessions WHERE cookie_token_hash = ?",
                (token_hash,),
            ).fetchone()
            if row is not None:
                conn.execute(
                    "UPDATE anonymous_sessions SET updated_at = ? WHERE id = ?",
                    (_utcnow_iso(), row["id"]),
                )
                conn.commit()
                return str(row["id"]), None

    if not create_if_missing:
        return None, None

    session_id = str(uuid.uuid4())
    token = secrets.token_urlsafe(32)
    token_hash = _hash_cookie_token(token)
    now = _utcnow_iso()
    with _db_connect() as conn:
        conn.execute(
            """
            INSERT INTO anonymous_sessions (id, cookie_token_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, token_hash, now, now),
        )
        conn.commit()

    return session_id, _build_session_cookie(token)


def _history_item_from_row(row: sqlite3.Row) -> dict[str, Any]:
    result = json.loads(str(row["result_json"]))
    return {
        "id": str(row["id"]),
        "created_at": str(row["created_at"]),
        "url": str(row["url"]),
        "result": result,
    }


def _handle_history_route(
    *,
    method: str,
    path: str,
    body: bytes,
    request_headers: dict[str, str] | None,
    response_headers: dict[str, str],
) -> tuple[int, dict[str, str], bytes]:
    base_path = "/api/v1/history"
    item_id: str | None = None
    if path != base_path:
        if not path.startswith(base_path + "/"):
            return (
                HTTPStatus.NOT_FOUND,
                response_headers,
                json_bytes(error_payload("not_found", "Route not found.")),
            )
        item_id = path[len(base_path) + 1 :].strip()
        if not item_id:
            return (
                HTTPStatus.NOT_FOUND,
                response_headers,
                json_bytes(error_payload("not_found", "Route not found.")),
            )

    if method == "GET":
        if item_id is not None:
            return (
                HTTPStatus.METHOD_NOT_ALLOWED,
                response_headers,
                json_bytes(
                    error_payload("method_not_allowed", "Use DELETE or OPTIONS.")
                ),
            )

        session_id, _ = _resolve_or_create_session(
            request_headers, create_if_missing=False
        )
        if not session_id:
            return HTTPStatus.OK, response_headers, json_bytes({"history": []})

        with _db_connect() as conn:
            rows = conn.execute(
                """
                SELECT id, created_at, url, result_json
                FROM search_history
                WHERE session_id = ?
                ORDER BY created_at DESC
                """,
                (session_id,),
            ).fetchall()
        history = [_history_item_from_row(row) for row in rows]
        return HTTPStatus.OK, response_headers, json_bytes({"history": history})

    if method == "POST":
        if item_id is not None:
            return (
                HTTPStatus.METHOD_NOT_ALLOWED,
                response_headers,
                json_bytes(
                    error_payload("method_not_allowed", "Use DELETE or OPTIONS.")
                ),
            )

        try:
            payload = parse_json_body(body)
        except json.JSONDecodeError:
            return (
                HTTPStatus.BAD_REQUEST,
                response_headers,
                json_bytes(
                    error_payload("invalid_json", "Request body must be valid JSON.")
                ),
            )

        url = payload.get("url")
        result = payload.get("result")

        if not isinstance(url, str) or not url.strip():
            return (
                HTTPStatus.BAD_REQUEST,
                response_headers,
                json_bytes(
                    error_payload("missing_url", "A non-empty 'url' value is required.")
                ),
            )

        if not isinstance(result, dict):
            return (
                HTTPStatus.BAD_REQUEST,
                response_headers,
                json_bytes(
                    error_payload(
                        "missing_result", "A JSON object 'result' value is required."
                    )
                ),
            )

        session_id, set_cookie = _resolve_or_create_session(
            request_headers, create_if_missing=True
        )
        assert session_id is not None

        item = {
            "id": str(uuid.uuid4()),
            "created_at": _utcnow_iso(),
            "url": url.strip(),
            "result": result,
        }

        with _db_connect() as conn:
            conn.execute(
                """
                INSERT INTO search_history (id, session_id, created_at, url, result_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    item["id"],
                    session_id,
                    item["created_at"],
                    item["url"],
                    json.dumps(item["result"]),
                ),
            )
            conn.commit()

        if set_cookie:
            response_headers["Set-Cookie"] = set_cookie

        return HTTPStatus.CREATED, response_headers, json_bytes({"item": item})

    if method == "DELETE":
        session_id, _ = _resolve_or_create_session(
            request_headers, create_if_missing=False
        )
        if not session_id:
            return HTTPStatus.NO_CONTENT, response_headers, b""

        with _db_connect() as conn:
            if item_id is None:
                conn.execute(
                    "DELETE FROM search_history WHERE session_id = ?", (session_id,)
                )
            else:
                conn.execute(
                    "DELETE FROM search_history WHERE session_id = ? AND id = ?",
                    (session_id, item_id),
                )
            conn.commit()

        return HTTPStatus.NO_CONTENT, response_headers, b""

    return (
        HTTPStatus.METHOD_NOT_ALLOWED,
        response_headers,
        json_bytes(
            error_payload("method_not_allowed", "Use GET, POST, DELETE, or OPTIONS.")
        ),
    )


def handle_api_request(
    *,
    method: str,
    path: str,
    query_string: str = "",
    body: bytes = b"",
    analyzer: Callable[[str], dict[str, Any]] = jobcarbon.analyze_url,
    request_headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], bytes]:
    headers, origin, origin_allowed = _build_headers(request_headers)

    if origin and not origin_allowed:
        return (
            HTTPStatus.FORBIDDEN,
            headers,
            json_bytes(
                error_payload("cors_origin_not_allowed", "Origin is not allowed.")
            ),
        )

    if method == "OPTIONS":
        return HTTPStatus.NO_CONTENT, headers, b""

    if path.startswith("/api/v1/history"):
        return _handle_history_route(
            method=method,
            path=path,
            body=body,
            request_headers=request_headers,
            response_headers=headers,
        )

    if method == "GET" and path == "/healthz":
        return (
            HTTPStatus.OK,
            headers,
            json_bytes({"ok": True, "service": "jobcarbon-api"}),
        )

    if path == "/api/v1/platforms":
        if method != "GET":
            return (
                HTTPStatus.METHOD_NOT_ALLOWED,
                headers,
                json_bytes(error_payload("method_not_allowed", "Use GET or OPTIONS.")),
            )
        return (
            HTTPStatus.OK,
            headers,
            json_bytes(
                {
                    "platforms": jobcarbon.list_platform_capabilities(),
                    "summary": jobcarbon.summarize_platform_capabilities(),
                }
            ),
        )

    if path != "/api/v1/estimate":
        return (
            HTTPStatus.NOT_FOUND,
            headers,
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
                headers,
                json_bytes(
                    error_payload("invalid_json", "Request body must be valid JSON.")
                ),
            )
        url = payload.get("url")
    else:
        return (
            HTTPStatus.METHOD_NOT_ALLOWED,
            headers,
            json_bytes(
                error_payload("method_not_allowed", "Use GET, POST, or OPTIONS.")
            ),
        )

    if not isinstance(url, str) or not url.strip():
        return (
            HTTPStatus.BAD_REQUEST,
            headers,
            json_bytes(
                error_payload("missing_url", "A non-empty 'url' value is required.")
            ),
        )

    try:
        result = analyzer(url.strip())
    except jobcarbon.InvalidURLError as exc:
        return (
            HTTPStatus.BAD_REQUEST,
            headers,
            json_bytes(error_payload("invalid_url", str(exc))),
        )
    except jobcarbon.HTTPRequestError as exc:
        return (
            HTTPStatus.BAD_GATEWAY,
            headers,
            json_bytes(error_payload("upstream_payload_error", str(exc))),
        )
    except jobcarbon.PageFetchError as exc:
        return (
            HTTPStatus.BAD_GATEWAY,
            headers,
            json_bytes(error_payload("upstream_fetch_failed", str(exc))),
        )
    except Exception as exc:  # pragma: no cover - defensive HTTP guard
        return (
            HTTPStatus.INTERNAL_SERVER_ERROR,
            headers,
            json_bytes(error_payload("internal_error", f"Unexpected error: {exc}")),
        )

    return HTTPStatus.OK, headers, json_bytes(result)


def run_stream_estimate(
    url: str,
    write: Callable[[bytes], None],
    *,
    analyzer: Callable[[str], dict[str, Any]] = jobcarbon.analyze_url,
) -> None:
    """
    Drive `analyzer(url)` with a progress emitter that serializes each event
    as an NDJSON line via `write`. Emits a terminal `result` or `error` event.
    """

    def emit(event: dict[str, Any]) -> None:
        try:
            line = (json.dumps(event) + "\n").encode("utf-8")
        except (TypeError, ValueError):
            return
        try:
            write(line)
        except Exception:
            # A dead client must not break analysis state; swallow write errors.
            pass

    token = jobcarbon.set_progress_emitter(emit)
    try:
        try:
            result = analyzer(url)
        except jobcarbon.InvalidURLError as exc:
            emit({"type": "error", "code": "invalid_url", "message": str(exc)})
            return
        except jobcarbon.HTTPRequestError as exc:
            emit(
                {
                    "type": "error",
                    "code": "upstream_payload_error",
                    "message": str(exc),
                }
            )
            return
        except jobcarbon.PageFetchError as exc:
            emit(
                {
                    "type": "error",
                    "code": "upstream_fetch_failed",
                    "message": str(exc),
                }
            )
            return
        except Exception as exc:  # pragma: no cover - defensive guard
            emit(
                {
                    "type": "error",
                    "code": "internal_error",
                    "message": f"Unexpected error: {exc}",
                }
            )
            return
        emit({"type": "result", "result": result})
    finally:
        jobcarbon.reset_progress_emitter(token)


def _stream_url_from_request(
    method: str, query_string: str, body: bytes
) -> tuple[str | None, dict[str, Any] | None]:
    """Return (url, error_payload). Exactly one is non-None."""
    if method == "GET":
        params = parse_qs(query_string)
        url = params.get("url", [None])[0]
    elif method == "POST":
        try:
            payload = parse_json_body(body)
        except json.JSONDecodeError:
            return None, error_payload(
                "invalid_json", "Request body must be valid JSON."
            )
        url = payload.get("url")
    else:
        return None, error_payload("method_not_allowed", "Use GET, POST, or OPTIONS.")

    if not isinstance(url, str) or not url.strip():
        return None, error_payload(
            "missing_url", "A non-empty 'url' value is required."
        )
    return url.strip(), None


class JobcarbonAPIHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self) -> None:  # noqa: N802
        self._handle()

    def do_GET(self) -> None:  # noqa: N802
        self._handle()

    def do_POST(self) -> None:  # noqa: N802
        self._handle()

    def do_DELETE(self) -> None:  # noqa: N802
        self._handle()

    def _handle(self) -> None:
        parsed = urlparse(self.path)
        body = b""
        if self.command in {"POST", "PUT", "PATCH"}:
            content_length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_length)

        if parsed.path == STREAM_PATH and self.command != "OPTIONS":
            self._handle_stream(parsed.query, body)
            return

        status, headers, payload = handle_api_request(
            method=self.command,
            path=parsed.path,
            query_string=parsed.query,
            body=body,
            request_headers=dict(self.headers.items()),
        )

        self.send_response(status)
        for name, value in headers.items():
            self.send_header(name, value)
        self.end_headers()
        if payload:
            self.wfile.write(payload)

    def _handle_stream(self, query_string: str, body: bytes) -> None:
        request_headers = dict(self.headers.items())
        cors_headers, origin, origin_allowed = _build_headers(request_headers)
        if origin and not origin_allowed:
            self.send_response(HTTPStatus.FORBIDDEN)
            for name, value in cors_headers.items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(
                json_bytes(
                    error_payload(
                        "cors_origin_not_allowed", "Origin is not allowed."
                    )
                )
            )
            return

        url, err = _stream_url_from_request(self.command, query_string, body)
        if err is not None:
            code = err["error"]["code"]
            if code == "method_not_allowed":
                status = HTTPStatus.METHOD_NOT_ALLOWED
            else:
                status = HTTPStatus.BAD_REQUEST
            self.send_response(status)
            for name, value in cors_headers.items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(json_bytes(err))
            return

        # Streaming headers: NDJSON, close-delimited (no Content-Length).
        self.send_response(HTTPStatus.OK)
        stream_headers = {
            k: v
            for k, v in cors_headers.items()
            if k not in {"Content-Type", "Content-Length"}
        }
        stream_headers["Content-Type"] = "application/x-ndjson; charset=utf-8"
        stream_headers["Cache-Control"] = "no-store"
        stream_headers["X-Accel-Buffering"] = "no"
        stream_headers["Connection"] = "close"
        for name, value in stream_headers.items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.flush()

        def write_line(data: bytes) -> None:
            self.wfile.write(data)
            self.wfile.flush()

        run_stream_estimate(url, write_line)
        self.close_connection = True

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
