"""WSGI entrypoint para Alwaysdata (sitio Python WSGI)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pad as padmod  # noqa: E402


def application(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET")
    path = environ.get("PATH_INFO", "/")
    if method == "GET" and (path == "/" or path == ""):
        body = padmod.EDITOR.encode()
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8"),
                                  ("Content-Length", str(len(body)))])
        return [body]
    if method == "GET" and path == "/health":
        body = b'{"ok": true}'
        start_response("200 OK", [("Content-Type", "application/json"),
                                  ("Content-Length", str(len(body)))])
        return [body]
    parts = path.strip("/").split("/", 1)
    if len(parts) == 2 and parts[0] in ("api", "read") and method == "GET":
        try:
            text = padmod.read_pad(parts[1])
        except ValueError:
            start_response("400 Bad Request", [("Content-Type", "text/plain")])
            return [b"id invalido"]
        if parts[0] == "api":
            body = text.encode()
            start_response("200 OK", [("Content-Type", "text/plain; charset=utf-8"),
                                      ("Content-Length", str(len(body)))])
            return [body]
        body = padmod.render_read(parts[1], text).encode()
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8"),
                                  ("Content-Length", str(len(body)))])
        return [body]
    if len(parts) == 2 and parts[0] == "api" and method == "POST":
        from urllib.parse import parse_qs

        query = parse_qs(environ.get("QUERY_STRING", ""))
        mode = (query.get("mode") or [""])[0]
        headers = {"X-Pad-Key": environ.get("HTTP_X_PAD_KEY", "")}
        if not padmod.key_ok(parts[1], headers):
            start_response("403 Forbidden", [("Content-Type", "text/plain")])
            return [b"key invalida o ausente (X-Pad-Key)"]
        try:
            if mode == "clear":
                padmod.clear_pad(parts[1])
                size = 0
            else:
                try:
                    length = int(environ.get("CONTENT_LENGTH") or "0")
                except ValueError:
                    length = 0
                if length > 64_000:
                    start_response("413 Too Large", [("Content-Type", "text/plain")])
                    return [b"demasiado grande"]
                raw = environ["wsgi.input"].read(length) if length else b""
                size = padmod.append_pad(parts[1], raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as e:
            start_response("400 Bad Request", [("Content-Type", "text/plain")])
            return [str(e).encode()]
        body = f'{{"ok": true, "size": {size}}}'.encode()
        start_response("200 OK", [("Content-Type", "application/json"),
                                  ("Content-Length", str(len(body)))])
        return [body]
    start_response("404 Not Found", [("Content-Type", "text/plain")])
    return [b"not found"]
