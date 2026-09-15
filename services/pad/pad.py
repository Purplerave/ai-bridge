#!/usr/bin/env python3
"""Pad compartido estilo ScratchThePad (stdlib only).

Un archivo .md por pad en data/<id>.md. Sin dependencias, sin build.

  GET  /api/<id>              -> texto del pad (text/plain)
  POST /api/<id>?mode=append  -> añade al final (exige X-Pad-Key)
  GET  /read/<id>             -> vista HTML legible
  GET  /                     -> editor mínimo (textarea + fetch)
  GET  /health               -> {"ok": true}

Env:
  PAD_DATA_DIR  donde viven los .md (defecto: ./data)
  PAD_KEYS      "id1:key1,id2:key2" (defecto: "" = escritura abierta, solo dev)
  PAD_HOST / PAD_PORT
"""

from __future__ import annotations

import html
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get("PAD_DATA_DIR") or (ROOT / "data"))
HOST = os.environ.get("PAD_HOST", "0.0.0.0")
PORT = int(os.environ.get("PAD_PORT") or os.environ.get("PORT") or "8090")
VERSION = "0.1.0"
MAX_PAD = 512_000
PAD_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")


def pad_keys() -> dict[str, str]:
    out: dict[str, str] = {}
    for pair in (os.environ.get("PAD_KEYS") or "").split(","):
        if ":" in pair:
            pid, key = pair.split(":", 1)
            if pid.strip() and key.strip():
                out[pid.strip()] = key.strip()
    return out


def pad_path(pid: str) -> Path:
    if not PAD_ID_RE.match(pid):
        raise ValueError("id de pad inválido")
    return DATA / f"{pid}.md"


def read_pad(pid: str) -> str:
    p = pad_path(pid)
    return p.read_text(encoding="utf-8") if p.exists() else ""


def append_pad(pid: str, text: str) -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    p = pad_path(pid)
    cur = read_pad(pid)
    add = text if text.endswith("\n") else text + "\n"
    if len(cur) + len(add) > MAX_PAD:
        raise ValueError("pad lleno (límite 512 KB)")
    p.write_text(cur + add, encoding="utf-8")
    return len(cur + add)


def clear_pad(pid: str) -> int:
    """Vacía el pad (borra el .md): el sello. Exige clave siempre."""
    DATA.mkdir(parents=True, exist_ok=True)
    p = pad_path(pid)
    p.write_text("", encoding="utf-8")
    return 0


def key_ok(pid: str, headers) -> bool:
    keys = pad_keys()
    if pid not in keys:
        return True  # pad sin key = abierto (solo dev/local)
    got = (headers.get("X-Pad-Key") or headers.get("x-pad-key") or "").strip()
    return bool(got) and got == keys[pid]


EDITOR = """<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pad</title>
<style>body{font-family:system-ui;max-width:72ch;margin:2em auto;padding:0 1em}
textarea{width:100%;height:50vh;font:1em/1.5 monospace}button{padding:.5em 1em}</style>
</head><body><h1>Pad <small id="pid"></small></h1>
<textarea id="t"></textarea><p><button onclick="save()">Guardar (append)</button>
<span id="st"></span></p>
<script>const id=location.hash.slice(1)||'demo';
document.getElementById('pid').textContent=id;
fetch('api/'+id).then(r=>r.text()).then(t=>document.getElementById('t').value=t);
function save(){const k=prompt('Write key:');if(k===null)return;
fetch('api/'+id+'?mode=append',{method:'POST',headers:{'X-Pad-Key':k,'Content-Type':'text/plain'},body:'\\n'+document.getElementById('t').value.split('\\n').slice(-20).join('\\n')})
.then(r=>document.getElementById('st').textContent=r.ok?'guardado':'error '+r.status);}</script>
</body></html>"""


def render_read(pid: str, text: str) -> str:
    paras = "".join(
        f"<p>{html.escape(p).replace(chr(10), '<br>')}</p>"
        for p in text.split("\n\n") if p.strip()
    )
    return (
        "<!doctype html><html lang='es'><head><meta charset='utf-8'>"
        f"<title>{html.escape(pid)} · pad</title></head><body>"
        f"<h1>{html.escape(pid)}</h1>{paras}</body></html>"
    )


class Handler(BaseHTTPRequestHandler):
    server_version = f"Pad/{VERSION}"

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body: bytes, ctype="text/plain; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if code != 204:
            self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        parts = u.path.strip("/").split("/", 1)
        if u.path in ("/", ""):
            return self._send(200, EDITOR.encode(), "text/html; charset=utf-8")
        if u.path == "/health":
            return self._send(200, b'{"ok": true}')
        if len(parts) == 2 and parts[0] in ("api", "read"):
            try:
                text = read_pad(parts[1])
            except ValueError:
                return self._send(400, b"id invalido")
            if parts[0] == "api":
                return self._send(200, text.encode("utf-8"))
            return self._send(200, render_read(parts[1], text).encode(), "text/html; charset=utf-8")
        return self._send(404, b"not found")

    def do_POST(self):
        u = urlparse(self.path)
        parts = u.path.strip("/").split("/", 1)
        if len(parts) != 2 or parts[0] != "api":
            return self._send(404, b"not found")
        pid = parts[1]
        mode = (parse_qs(u.query).get("mode") or [""])[0]
        try:
            pad_path(pid)
        except ValueError:
            return self._send(400, b"id invalido")
        if not key_ok(pid, self.headers):
            return self._send(403, b"key invalida o ausente (X-Pad-Key)")
        if mode == "clear":
            try:
                clear_pad(pid)
            except ValueError as e:
                return self._send(400, str(e).encode())
            return self._send(200, b'{"ok": true, "cleared": true}', "application/json")
        length = int(self.headers.get("Content-Length") or "0")
        if length > 64_000:
            return self._send(413, b"demasiado grande")
        raw = self.rfile.read(length) if length else b""
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return self._send(400, b"solo utf-8")
        try:
            size = append_pad(pid, text)
        except ValueError as e:
            return self._send(400, str(e).encode())
        return self._send(200, f'{{"ok": true, "size": {size}}}'.encode(), "application/json")


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / ".gitkeep").touch(exist_ok=True)
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"pad {VERSION} on http://{HOST}:{PORT}", flush=True)
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
