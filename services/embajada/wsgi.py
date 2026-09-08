"""WSGI entrypoint para Alwaysdata (tipo de sitio: Python WSGI).

/          → portal HTML
/api       → descripción JSON
/health    → JSON
/msgs      → JSON
/msg       → POST JSON
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.parse import parse_qs

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app as emb  # noqa: E402

_PORTAL = (ROOT / "portal.html").read_text(encoding="utf-8")


def _read_body(environ) -> bytes:
    try:
        length = int(environ.get("CONTENT_LENGTH") or "0")
    except ValueError:
        length = 0
    if length <= 0:
        return b""
    return environ["wsgi.input"].read(length)


def _headers_from_environ(environ) -> dict:
    h = {}
    auth = environ.get("HTTP_AUTHORIZATION")
    if auth:
        h["Authorization"] = auth
    tok = environ.get("HTTP_X_EMBAJADA_TOKEN")
    if tok:
        h["X-Embajada-Token"] = tok
    return h


def _json_response(start_response, code: int, payload: dict):
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    status = {
        200: "200 OK",
        201: "201 Created",
        204: "204 No Content",
        400: "400 Bad Request",
        401: "401 Unauthorized",
        404: "404 Not Found",
        413: "413 Payload Too Large",
    }.get(code, f"{code} Error")
    start_response(
        status,
        [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("Access-Control-Allow-Origin", "*"),
            ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
            (
                "Access-Control-Allow-Headers",
                "Content-Type, Authorization, X-Embajada-Token",
            ),
        ],
    )
    return [body]


def _html_response(start_response, html: str):
    body = html.encode("utf-8")
    start_response(
        "200 OK",
        [
            ("Content-Type", "text/html; charset=utf-8"),
            ("Content-Length", str(len(body))),
        ],
    )
    return [body]


def application(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET").upper()
    path = environ.get("PATH_INFO", "") or "/"
    path = path.rstrip("/") or "/"

    if method == "OPTIONS":
        start_response(
            "204 No Content",
            [
                ("Access-Control-Allow-Origin", "*"),
                ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
                (
                    "Access-Control-Allow-Headers",
                    "Content-Type, Authorization, X-Embajada-Token",
                ),
                ("Content-Length", "0"),
            ],
        )
        return [b""]

    if method == "GET" and path == "/":
        return _html_response(start_response, _PORTAL)

    if method == "GET" and path == "/api":
        return _json_response(
            start_response,
            200,
            {
                "service": "embajada",
                "version": getattr(emb, "VERSION", "wsgi"),
                "via": "wsgi",
                "docs": {
                    "portal": "GET /",
                    "health": "GET /health",
                    "list": "GET /msgs",
                    "post": "POST /msg",
                },
            },
        )

    if method == "GET" and path == "/health":
        return _json_response(
            start_response,
            200,
            {
                "ok": True,
                "service": "embajada",
                "version": getattr(emb, "VERSION", "wsgi"),
                "auth": bool((os.environ.get("EMBAJADA_TOKEN") or "").strip()),
                "via": "wsgi",
            },
        )

    if method == "GET" and path == "/msgs":
        qs = parse_qs(environ.get("QUERY_STRING") or "")
        try:
            limit = int((qs.get("limit") or ["50"])[0])
        except ValueError:
            limit = 50
        msgs = emb.read_msgs(limit=limit)
        return _json_response(
            start_response, 200, {"messages": msgs, "count": len(msgs)}
        )

    if method == "POST" and path == "/msg":
        if not emb.token_ok(_headers_from_environ(environ)):
            return _json_response(
                start_response, 401, {"ok": False, "error": "unauthorized"}
            )
        raw = _read_body(environ)
        if len(raw) > emb.MAX_BODY + 1024:
            return _json_response(
                start_response, 413, {"ok": False, "error": "payload too large"}
            )
        try:
            record = emb.normalize_payload(
                raw, environ.get("CONTENT_TYPE") or ""
            )
            saved = emb.append_msg(record)
        except (ValueError, json.JSONDecodeError) as e:
            return _json_response(
                start_response, 400, {"ok": False, "error": str(e)}
            )
        return _json_response(
            start_response, 201, {"ok": True, "message": saved}
        )

    return _json_response(start_response, 404, {"ok": False, "error": "not found"})
