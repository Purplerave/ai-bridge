"""Repartidor WSGI: /pad/* -> pad, resto -> Embajada.

Un solo sitio Alwaysdata sirve las dos apps. Sin dependencias.

Panel: Tipo Python WSGI, Aplicacion = services/despacho/wsgi.py,
directorio de trabajo = services/despacho/.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PAD_WSGI = ROOT.parent / "pad" / "wsgi.py"
EMB_WSGI = ROOT.parent / "embajada" / "wsgi.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.application


_pad_app = _load("despacho_pad", PAD_WSGI)
_emb_app = _load("despacho_emb", EMB_WSGI)


def application(environ, start_response):
    path = environ.get("PATH_INFO", "/")
    if path == "/pad" or path.startswith("/pad/"):
        environ = dict(environ)
        environ["PATH_INFO"] = path[4:] or "/"
        environ["SCRIPT_NAME"] = (environ.get("SCRIPT_NAME") or "") + "/pad"
        return _pad_app(environ, start_response)
    return _emb_app(environ, start_response)
