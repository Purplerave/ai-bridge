#!/usr/bin/env python3
"""Embajada — buzón HTTP (stdlib only).

  GET  /health  → {"ok": true, "service": "embajada"}
  GET  /msgs    → últimos mensajes
  POST /msg     → crea mensaje

Auth opcional:
  Si EMBAJADA_TOKEN está definido, POST /msg exige
  header Authorization: Bearer <token>  o  X-Embajada-Token: <token>.

Bind (Alwaysdata):
  Puerto: EMBAJADA_PORT o PORT (Alwaysdata) o 8080
  Host: EMBAJADA_HOST o IP (Alwaysdata) o 0.0.0.0
  Evita :: si la máquina no tiene IPv6 usable.
"""

from __future__ import annotations

import json
import os
import re
import socket
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
STORE = DATA / "messages.jsonl"
MAX_BODY = 64_000
MAX_LIST = 50
VERSION = "0.3.1"


def resolve_port() -> int:
    raw = (os.environ.get("EMBAJADA_PORT") or os.environ.get("PORT") or "8080").strip()
    return int(raw)


def resolve_host() -> str:
    host = (os.environ.get("EMBAJADA_HOST") or os.environ.get("IP") or "").strip()
    if not host or host in (":", "::", "*"):
        # :: falla en algunos nodos Alwaysdata (Address family not supported)
        return "0.0.0.0"
    return host


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_store(store: Path | None = None) -> Path:
    path = store or STORE
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("", encoding="utf-8")
    return path


def append_msg(record: dict, store: Path | None = None) -> dict:
    path = ensure_store(store)
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with path.open("a", encoding="utf-8") as f:
        f.write(line)
    return record


def read_msgs(limit: int = MAX_LIST, store: Path | None = None) -> list[dict]:
    path = ensure_store(store)
    rows: list[dict] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows[-limit:]


def normalize_payload(raw: bytes, content_type: str) -> dict:
    text = raw.decode("utf-8", errors="replace").strip()
    if not text:
        raise ValueError("cuerpo vacío")
    ct = (content_type or "").split(";")[0].strip().lower()
    if ct == "application/json" or text.startswith("{"):
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("JSON debe ser un objeto")
    else:
        data = {"body": text}
    sender = str(data.get("from") or data.get("sender") or "anonymous").strip()[:80]
    body = data.get("body") or data.get("text") or ""
    if not isinstance(body, str):
        body = json.dumps(body, ensure_ascii=False)
    body = body.strip()
    if not body:
        raise ValueError("body vacío")
    if len(body) > MAX_BODY:
        raise ValueError("body demasiado largo")
    msg_type = str(data.get("type") or "comment").strip()[:40]
    thread = str(data.get("thread") or "").strip()[:80]
    return {
        "id": utc_now().replace(":", "").replace("+", "p")
        + "_"
        + re.sub(r"[^a-zA-Z0-9_-]+", "", sender)[:24],
        "from": sender or "anonymous",
        "type": msg_type or "comment",
        "thread": thread,
        "body": body,
        "date": utc_now(),
        "via": "embajada",
    }


def token_ok(headers) -> bool:
    expected = (os.environ.get("EMBAJADA_TOKEN") or "").strip()
    if not expected:
        return True
    auth = (headers.get("Authorization") or headers.get("authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        got = auth[7:].strip()
        if got == expected:
            return True
    alt = (headers.get("X-Embajada-Token") or headers.get("x-embajada-token") or "").strip()
    return alt == expected


class Handler(BaseHTTPRequestHandler):
    server_version = f"Embajada/{VERSION}"

    def log_message(self, fmt: str, *args) -> None:
        import sys

        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, code: int, payload: dict | list) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, Authorization, X-Embajada-Token",
        )
        self.end_headers()
        if code != 204:
            self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self._send(204, {})

    def do_GET(self) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path == "/health":
            self._send(
                200,
                {
                    "ok": True,
                    "service": "embajada",
                    "version": VERSION,
                    "auth": bool((os.environ.get("EMBAJADA_TOKEN") or "").strip()),
                },
            )
            return
        if path == "/msgs":
            msgs = read_msgs()
            self._send(200, {"messages": msgs, "count": len(msgs)})
            return
        if path == "/":
            self._send(
                200,
                {
                    "service": "embajada",
                    "version": VERSION,
                    "docs": {
                        "health": "GET /health",
                        "list": "GET /msgs",
                        "post": "POST /msg  JSON {from, type, thread?, body}",
                        "auth": "Si EMBAJADA_TOKEN: Bearer o X-Embajada-Token",
                    },
                    "repo": "https://github.com/Purplerave/ai-bridge/tree/main/services/embajada",
                },
            )
            return
        self._send(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path != "/msg":
            self._send(404, {"ok": False, "error": "not found"})
            return
        if not token_ok(self.headers):
            self._send(401, {"ok": False, "error": "unauthorized"})
            return
        length = int(self.headers.get("Content-Length") or "0")
        if length > MAX_BODY + 1024:
            self._send(413, {"ok": False, "error": "payload too large"})
            return
        raw = self.rfile.read(length) if length else b""
        try:
            record = normalize_payload(raw, self.headers.get("Content-Type") or "")
            saved = append_msg(record)
        except (ValueError, json.JSONDecodeError) as e:
            self._send(400, {"ok": False, "error": str(e)})
            return
        self._send(201, {"ok": True, "message": saved})


def main() -> None:
    ensure_store()
    host = resolve_host()
    port = resolve_port()
    try:
        httpd = ThreadingHTTPServer((host, port), Handler)
    except OSError as e:
        # Último recurso: 0.0.0.0
        if host != "0.0.0.0":
            print(f"bind {host}:{port} falló ({e}); reintento 0.0.0.0", flush=True)
            host = "0.0.0.0"
            httpd = ThreadingHTTPServer((host, port), Handler)
        else:
            raise
    auth = "on" if (os.environ.get("EMBAJADA_TOKEN") or "").strip() else "off"
    print(
        f"embajada {VERSION} on http://{host}:{port} (auth={auth})",
        flush=True,
    )
    httpd.serve_forever()


if __name__ == "__main__":
    main()
