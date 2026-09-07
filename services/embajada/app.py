#!/usr/bin/env python3
"""Embajada — buzón HTTP mínimo (stdlib only).

Pensado para Alwaysdata / cualquier host con Python.
GitHub sigue siendo el archivo; esto es el canal fácil.

  GET  /health  → {"ok": true, "service": "embajada"}
  GET  /msgs    → últimos mensajes (jsonl en data/)
  POST /msg     → cuerpo JSON o texto plano → guarda en data/messages.jsonl

Uso local:
  python app.py
  # http://127.0.0.1:8080/health
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
STORE = DATA / "messages.jsonl"
HOST = os.environ.get("EMBAJADA_HOST", "0.0.0.0")
PORT = int(os.environ.get("EMBAJADA_PORT", "8080"))
MAX_BODY = 64_000
MAX_LIST = 50


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_store() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    if not STORE.exists():
        STORE.write_text("", encoding="utf-8")


def append_msg(record: dict) -> dict:
    ensure_store()
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with STORE.open("a", encoding="utf-8") as f:
        f.write(line)
    return record


def read_msgs(limit: int = MAX_LIST) -> list[dict]:
    ensure_store()
    rows: list[dict] = []
    try:
        text = STORE.read_text(encoding="utf-8")
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
        "id": utc_now().replace(":", "").replace("+", "p") + "_" + re.sub(r"[^a-zA-Z0-9_-]+", "", sender)[:24],
        "from": sender or "anonymous",
        "type": msg_type or "comment",
        "thread": thread,
        "body": body,
        "date": utc_now(),
        "via": "embajada",
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "Embajada/0.1"

    def log_message(self, fmt: str, *args) -> None:
        sys_stderr = __import__("sys").stderr
        sys_stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, code: int, payload: dict | list, extra_headers: dict | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self._send(204, {})

    def do_GET(self) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path == "/health":
            self._send(200, {"ok": True, "service": "embajada", "version": "0.1"})
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
                    "docs": {
                        "health": "GET /health",
                        "list": "GET /msgs",
                        "post": "POST /msg  JSON {from, type, thread?, body}",
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
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"embajada listening on http://{HOST}:{PORT}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
