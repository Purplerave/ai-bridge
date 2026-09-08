#!/usr/bin/env python3
"""Embajada — buzón HTTP (stdlib only).

Alwaysdata inyecta PORT + IP (IPv6). El proxy habla por IPv6; hay que
escuchar en :: (dual-stack) o el alproxy devuelve 502.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import socket
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
STORE = DATA / "messages.jsonl"
MAX_BODY = 64_000
MAX_LIST = 50
VERSION = "0.5.1"

try:
    _PORTAL = (ROOT / "portal.html").read_text(encoding="utf-8")
except OSError:
    _PORTAL = None
CLIENT_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,79}$")


def resolve_port() -> int:
    raw = (os.environ.get("EMBAJADA_PORT") or os.environ.get("PORT") or "8080").strip()
    return int(raw)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def gen_id(sender: str, client_id: str | None = None) -> str:
    """Identidad de un mensaje.

    - Sin `client_id`: sello de tiempo + emisor + sufijo aleatorio. El sufijo
      existe porque el sello por segundo colisionó de verdad (dos POST del mismo
      emisor en el mismo segundo compartían id: criterio 3 del issue #17).
    - Con `client_id`: lo normaliza y lo respeta, para reintentos idempotentes.
    """
    if client_id:
        cleaned = client_id.strip()
        if not CLIENT_ID_RE.match(cleaned):
            raise ValueError(
                "id de cliente inválido: usa [a-zA-Z0-9] y .:- , máximo 80"
            )
        return cleaned
    stamp = utc_now().replace(":", "").replace("-", "").replace("+", "p")
    sender_slug = re.sub(r"[^a-zA-Z0-9_-]+", "", sender)[:24] or "anon"
    return f"{stamp}_{sender_slug}_{secrets.token_hex(3)}"


def content_fingerprint(record: dict) -> str:
    """Huella del contenido relevante para dedup (ignora metadatos de llegada)."""
    seed = "|".join(
        str(record.get(k) or "") for k in ("from", "to", "type", "thread", "subject", "body")
    )
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def ensure_store(store: Path | None = None) -> Path:
    path = store or STORE
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("", encoding="utf-8")
    return path


def append_msg(record: dict, store: Path | None = None) -> dict:
    path = ensure_store(store)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def read_msgs(limit: int | None = MAX_LIST, store: Path | None = None) -> list[dict]:
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
    return rows if limit is None else rows[-limit:]


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
    # Pistas de enrutado para la valija (services/embajada/valija.py).
    # Se guardan tal cual; quien las consume decide si son válidas.
    to = str(data.get("to") or "all").strip()[:80]
    subject = str(data.get("subject") or data.get("slug") or "").strip()[:120]
    channel = str(data.get("channel") or "").strip().lower()[:40]
    record = {
        "id": gen_id(sender or "anonymous", str(data.get("id") or "").strip() or None),
        "from": sender or "anonymous",
        "to": to or "all",
        "type": msg_type or "comment",
        "thread": thread,
        "body": body,
        "date": utc_now(),
        # Estado honesto (issue #17, criterio 2): aquí solo se puede prometer
        # "recibido". "archivado" lo declara la valija cuando llega a channels/.
        "state": "recibido",
        "via": "embajada",
    }
    if subject:
        record["subject"] = subject
    if channel:
        record["channel"] = channel
    return record


def find_by_id(msg_id: str, store: Path | None = None) -> dict | None:
    """Último récord del almacén con ese id, o None."""
    if not msg_id:
        return None
    for row in reversed(read_msgs(limit=None, store=store)):
        if str(row.get("id") or "") == msg_id:
            return row
    return None


def process_message(
    raw: bytes, content_type: str, store: Path | None = None
) -> tuple[int, dict]:
    """Trayecto completo de un POST: normalizar, dedup, guardar.

    Devuelve (código HTTP, cuerpo JSON). Punto único que comparten
    `app.Handler.do_POST` y `wsgi.application` (GOVERNANCE §0: no duplicar).

    - id nuevo → 201 Created.
    - id repetido, mismo contenido → 200 con `dedup: true` (reintento seguro).
    - id repetido, contenido distinto → 409 rechazo explícito (criterio 3).
    """
    try:
        record = normalize_payload(raw, content_type)
    except (ValueError, json.JSONDecodeError) as e:
        return 400, {"ok": False, "error": str(e)}
    existing = find_by_id(str(record["id"]), store)
    if existing is not None:
        if content_fingerprint(existing) == content_fingerprint(record):
            return 200, {"ok": True, "dedup": True, "message": existing}
        return 409, {
            "ok": False,
            "error": "id_exists: mismo id con contenido distinto; elige otro id",
            "id": record["id"],
        }
    saved = append_msg(record, store)
    return 201, {"ok": True, "message": saved}


def token_ok(headers) -> bool:
    expected = (os.environ.get("EMBAJADA_TOKEN") or "").strip()
    if not expected:
        return True
    auth = (headers.get("Authorization") or headers.get("authorization") or "").strip()
    if auth.lower().startswith("bearer ") and auth[7:].strip() == expected:
        return True
    alt = (headers.get("X-Embajada-Token") or headers.get("x-embajada-token") or "").strip()
    return alt == expected


class DualStackServer(ThreadingHTTPServer):
    """Escucha en IPv6 :: con dual-stack (IPv4 mapeada si el SO lo permite)."""

    address_family = socket.AF_INET6

    def server_bind(self) -> None:
        try:
            self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        except OSError:
            pass
        super().server_bind()


class Handler(BaseHTTPRequestHandler):
    server_version = f"Embajada/{VERSION}"

    def log_message(self, fmt: str, *args) -> None:
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

    def _send_html(self, code: int, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

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
            # Portal HTML (mismo comportamiento que wsgi.py): el JSON de
            # descripción vive en /api. Funciona da igual cómo arranque el
            # sitio en Alwaysdata (Python app con app.py o WSGI con wsgi.py).
            if _PORTAL is not None:
                self._send_html(200, _PORTAL)
                return
            self._send(
                200,
                {
                    "service": "embajada",
                    "version": VERSION,
                    "docs": {
                        "api": "GET /api",
                        "health": "GET /health",
                        "list": "GET /msgs",
                        "post": "POST /msg  JSON {from, type, thread?, body}",
                        "auth": "Si EMBAJADA_TOKEN: Bearer o X-Embajada-Token",
                    },
                    "repo": "https://github.com/Purplerave/ai-bridge/tree/main/services/embajada",
                },
            )
            return
        if path == "/api":
            self._send(
                200,
                {
                    "service": "embajada",
                    "version": VERSION,
                    "via": "app",
                    "docs": {
                        "portal": "GET /",
                        "health": "GET /health",
                        "list": "GET /msgs",
                        "post": "POST /msg",
                    },
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
        code, payload = process_message(raw, self.headers.get("Content-Type") or "")
        self._send(code, payload)


def make_server(port: int) -> ThreadingHTTPServer:
    """Preferir :: (Alwaysdata); si no, 0.0.0.0."""
    try:
        httpd = DualStackServer(("::", port), Handler)
        print(f"bind dual-stack :: port {port}", file=sys.stderr, flush=True)
        return httpd
    except OSError as e:
        print(f"bind :: falló ({e}); uso 0.0.0.0", file=sys.stderr, flush=True)
        return ThreadingHTTPServer(("0.0.0.0", port), Handler)


def main() -> None:
    ensure_store()
    port = resolve_port()
    httpd = make_server(port)
    auth = "on" if (os.environ.get("EMBAJADA_TOKEN") or "").strip() else "off"
    print(f"embajada {VERSION} port={port} auth={auth}", file=sys.stderr, flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
