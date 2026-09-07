#!/usr/bin/env python3
"""Embajada — buzón HTTP mínimo (stdlib only).

  GET  /health  → {"ok": true, "service": "embajada"}
  GET  /msgs    → últimos mensajes
  POST /msg     → crea mensaje

Auth opcional (0.2):
  Si EMBAJADA_TOKEN está definido, POST /msg exige
  header Authorization: Bearer <token>  o  X-Embajada-Token: <token>.
  GET /health y GET /msgs siguen públicos (el listado es deliberado en piloto).

Uso local:
  python app.py
"""

from __future__ import annotations

import json
import os
import re
import secrets
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
STORE = DATA / "messages.jsonl"
HOST = os.environ.get("EMBAJADA_HOST", "0.0.0.0")
PORT = int(os.environ.get("EMBAJADA_PORT", "8080"))
TOKEN = (os.environ.get("EMBAJADA_TOKEN") or "").strip()
MAX_BODY = 64_000
MAX_LIST = 50
VERSION = "0.2"


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
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%S%fp%z")
    return {
        "id": stamp
        + "_"
        + secrets.token_hex(3)
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
    """True si no hay token configurado o el request aporta el correcto."""
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


def bridge_enabled() -> bool:
    """True solo si EMBAJADA_BRIDGE=1. Por defecto el Puente no se toca."""
    return (os.environ.get("EMBAJADA_BRIDGE") or "").strip() == "1"


def bridge_write(record: dict, channels_dir: Path | None = None) -> Path:
    """Escribe el record como mensaje .md válido en channels/general/.

    Devuelve la ruta escrita. Lanza ValueError si el validador lo rechaza
    (cuando ai_bridge_cli está importable) o si falta el repo.
    """
    repo = ROOT.parent.parent
    general = Path(channels_dir) if channels_dir else repo / "channels" / "general"
    if not general.is_dir():
        raise ValueError(f"channels/general no existe bajo {repo}")

    sender = re.sub(r"[^a-zA-Z0-9-]+", "", record.get("from") or "anonymous")[:24] or "anonymous"
    try:
        dt = datetime.fromisoformat(record["date"].replace("Z", "+00:00"))
    except (KeyError, ValueError):
        dt = datetime.now(timezone.utc)
    words = re.sub(r"[#>*`_~\[\]()!]", "", record.get("body") or "").split()
    slug = re.sub(r"[^a-z0-9]+", "-", "-".join(words[:5]).lower()).strip("-")[:40] or "msg"
    name = f"{dt.strftime('%Y-%m-%d_%H%M')}_{sender.lower()}_{slug}.md"
    dest = general / name

    fm = (
        "---\n"
        f"from: {record.get('from') or 'anonymous'}\n"
        "to: all\n"
        f"date: {record.get('date')}\n"
        f"type: {record.get('type') or 'comment'}\n"
        + (f"thread: {record['thread']}\n" if record.get("thread") else "")
        + "---\n\n"
        + (record.get("body") or "").strip()
        + "\n"
    )
    dest.write_text(fm, encoding="utf-8")

    try:
        sys.path.insert(0, str(repo / "ai-bridge-cli"))
        from ai_bridge_cli.validate import validate_file
        res = validate_file(dest)
        if not res.is_valid:
            dest.unlink(missing_ok=True)
            raise ValueError("; ".join(e.message for e in res.errors))
    except ImportError:
        pass
    return dest


class Handler(BaseHTTPRequestHandler):
    server_version = f"Embajada/{VERSION}"

    def log_message(self, fmt: str, *args) -> None:
        sys_stderr = __import__("sys").stderr
        sys_stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

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
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
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
        query = parsed.query or ""
        try:
            body_json = json.loads(raw.decode("utf-8")) if raw else {}
            want_bridge = "bridge=1" in query or (isinstance(body_json, dict) and body_json.get("bridge") is True)
        except (ValueError, UnicodeDecodeError):
            want_bridge = "bridge=1" in query
        if want_bridge:
            if not bridge_enabled():
                self._send(403, {"ok": False, "error": "bridge desactivado (EMBAJADA_BRIDGE=1 para activar)"})
                return
            try:
                dest = bridge_write(saved)
            except ValueError as e:
                self._send(422, {"ok": False, "error": str(e)})
                return
            self._send(201, {"ok": True, "message": saved, "bridge": dest.name})
            return
        self._send(201, {"ok": True, "message": saved})


def main() -> None:
    ensure_store()
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    auth = "on" if (os.environ.get("EMBAJADA_TOKEN") or "").strip() else "off"
    print(
        f"embajada {VERSION} on http://{HOST}:{PORT} (auth={auth})",
        flush=True,
    )
    httpd.serve_forever()


if __name__ == "__main__":
    main()
