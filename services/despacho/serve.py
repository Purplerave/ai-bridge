#!/usr/bin/env python3
"""Repartidor HTTP: /pad/* -> pad, resto -> Embajada. Un solo puerto.

Uso (Alwaysdata, tipo Programa de usuario):
  sh -c 'export PORT=$PORT; exec python3 services/despacho/serve.py'

Env: PORT, EMBAJADA_TOKEN, EMBAJADA_BRIDGE, PAD_KEYS, PAD_DATA_DIR.
"""

from __future__ import annotations

import os
import socket
import sys
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for p in (str(ROOT.parent / "pad"), str(ROOT.parent / "embajada")):
    if p not in sys.path:
        sys.path.insert(0, p)

import pad as padmod  # noqa: E402
import app as emb  # noqa: E402


class Handler(padmod.Handler):
    def do_GET(self):
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        if path == "/pad" or path.startswith("/pad/"):
            # Reescribe /pad/api/x -> /api/x para la app del pad.
            sub = path[4:] or "/"
            q = self.path.split("?", 1)
            self.path = sub + ("?" + q[1] if len(q) > 1 else "")
            return padmod.Handler.do_GET(self)
        return self._emb("GET")

    def do_POST(self):
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        if path.startswith("/pad/"):
            sub = path[4:] or "/"
            q = self.path.split("?", 1)
            self.path = sub + ("?" + q[1] if len(q) > 1 else "")
            return padmod.Handler.do_POST(self)
        return self._emb("POST")

    def do_OPTIONS(self):
        return self._emb("OPTIONS")

    def _emb(self, method: str):
        # Delega en el Handler de la Embajada con el path intacto.
        handler = emb.Handler.__new__(emb.Handler)
        handler.__dict__.update(self.__dict__)
        return getattr(emb.Handler, f"do_{method}")(handler)


class DualStackServer(ThreadingHTTPServer):
    address_family = socket.AF_INET6

    def server_bind(self) -> None:
        try:
            self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        except OSError:
            pass
        super().server_bind()


def main() -> int:
    port = int(os.environ.get("EMBAJADA_PORT") or os.environ.get("PORT") or "8100")
    try:
        httpd = DualStackServer(("::", port), Handler)
    except OSError:
        httpd = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"despacho on port {port} (embajada + pad)", flush=True)
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
