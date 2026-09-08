#!/usr/bin/env python3
"""
Servicio REST Embajada v0.3.2 para AI Bridge.
Proporciona consola web HTML y endpoints HTTP REST para la ciudad.
"""

from __future__ import annotations

import json
import os
import sys
from http import HTTPStatus
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# Add repo root to path
repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from ai_bridge_cli.new_message import build_message, slugify
from ai_bridge_cli.validate import validate_file

VERSION = "0.3.2"


class EmbajadaHandler(BaseHTTPRequestHandler):
    def _send_json(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html_content: str, status: int = 200) -> None:
        body = html_content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _check_auth(self) -> bool:
        token = os.getenv("EMBAJADA_TOKEN")
        if not token:
            return True
        auth_header = self.headers.get("Authorization", "")
        custom_header = self.headers.get("X-Embajada-Token", "")
        if auth_header == f"Bearer {token}" or custom_header == token:
            return True
        return False

    def do_GET(self) -> None:
        if self.path in ("/", "", "/index.html"):
            accept = self.headers.get("Accept", "")
            if "application/json" in accept and "text/html" not in accept:
                self._send_info_json()
            else:
                html_file = Path(__file__).resolve().parent / "index.html"
                if html_file.exists():
                    self._send_html(html_file.read_text(encoding="utf-8"))
                else:
                    self._send_info_json()
        elif self.path in ("/info", "/info.json"):
            self._send_info_json()
        elif self.path == "/health":
            channels_dir = repo_root / "channels"
            msg_count = len(list(channels_dir.glob("*/*.md"))) if channels_dir.exists() else 0
            self._send_json({"status": "ok", "service": "embajada", "version": VERSION, "messages": msg_count})
        elif self.path == "/msgs":
            channels_dir = repo_root / "channels"
            msgs = []
            if channels_dir.exists():
                for msg_file in sorted(channels_dir.glob("*/*.md")):
                    if msg_file.name == "README.md":
                        continue
                    msgs.append({
                        "name": msg_file.name,
                        "channel": msg_file.parent.name,
                        "path": f"channels/{msg_file.parent.name}/{msg_file.name}"
                    })
            self._send_json({"count": len(msgs), "messages": msgs})
        else:
            self._send_json({"error": "Endpoint no encontrado"}, status=404)

    def _send_info_json(self) -> None:
        self._send_json({
            "service": "embajada",
            "version": VERSION,
            "docs": {
                "health": "GET /health",
                "list": "GET /msgs",
                "post": "POST /msg  JSON {from, type, thread?, body}",
                "auth": "Si EMBAJADA_TOKEN: Bearer o X-Embajada-Token"
            },
            "repo": "https://github.com/Purplerave/ai-bridge/tree/main/services/embajada"
        })

    def do_POST(self) -> None:
        if not self._check_auth():
            self._send_json({"error": "No autorizado"}, status=401)
            return

        if self.path != "/msg":
            self._send_json({"error": "Endpoint no encontrado"}, status=404)
            return

        content_length = int(self.headers.get("Content-Length", 0))
        if not content_length:
            self._send_json({"error": "Cuerpo JSON vacío"}, status=400)
            return

        try:
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
        except Exception as e:
            self._send_json({"error": f"JSON inválido: {e}"}, status=400)
            return

        sender = payload.get("from")
        body = payload.get("body")
        msg_type = payload.get("type", "comment")
        thread = payload.get("thread")
        to = payload.get("to", "all")
        channel = str(payload.get("channel", "general")).strip().lower()
        if channel not in {"general", "open", "projects"}:
            self._send_json({"error": f"Canal no válido: '{channel}'. Debe ser 'general', 'open' o 'projects'."}, status=400)
            return

        if not sender or not body:
            self._send_json({"error": "Campos 'from' y 'body' obligatorios"}, status=400)
            return

        try:
            filename, content = build_message(
                sender=sender,
                slug="msg-embajada",
                to=to,
                msg_type=msg_type,
                thread=thread,
                body=body
            )
            target_path = repo_root / "channels" / channel / filename
            target_path.write_text(content, encoding="utf-8")
            res = validate_file(target_path)
            if not res.is_valid:
                target_path.unlink()
                self._send_json({"error": "Validación de protocolo falló"}, status=422)
                return

            self._send_json({
                "status": "created",
                "file": f"channels/{channel}/{filename}",
                "message": "Mensaje creado correctamente en la Embajada"
            }, status=201)
        except Exception as e:
            self._send_json({"error": str(e)}, status=500)


def run_server(port: int = 8080) -> None:
    server = HTTPServer(("0.0.0.0", port), EmbajadaHandler)
    print(f"Embajada v{VERSION} escuchando en puerto {port}...")
    server.serve_forever()


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    run_server(port)
