"""Tests del repartidor (WSGI sin red)."""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

SYS_DIR = Path(__file__).resolve().parent
REPO = SYS_DIR.parent.parent

os.environ["PAD_DATA_DIR"] = tempfile.mkdtemp()

spec = importlib.util.spec_from_file_location(
    "despacho_app", SYS_DIR / "wsgi.py")
despacho = importlib.util.module_from_spec(spec)
spec.loader.exec_module(despacho)


def call(app, method="GET", path="/", body=b"", headers=None):
    env = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "CONTENT_LENGTH": str(len(body)),
        "wsgi.input": __import__("io").BytesIO(body),
    }
    for k, v in (headers or {}).items():
        env["HTTP_" + k.upper().replace("-", "_")] = v
    out = {}

    def start_response(status, response_headers):
        out["status"] = status

    data = b"".join(app(env, start_response))
    return out["status"], data


class DespachoTests(unittest.TestCase):
    def test_pad_health(self):
        status, body = call(despacho.application, path="/pad/health")
        self.assertTrue(status.startswith("200"))
        self.assertIn(b'"ok": true', body)

    def test_pad_roundtrip(self):
        os.environ["PAD_KEYS"] = "t1:c1"
        try:
            status, _ = call(
                despacho.application, method="POST", path="/pad/api/t1",
                body="hola despacho".encode(),
                headers={"X-Pad-Key": "c1", "Content-Type": "text/plain"})
            self.assertTrue(status.startswith("200"), status)
            status, body = call(despacho.application, path="/pad/api/t1")
            self.assertIn(b"hola despacho", body)
        finally:
            os.environ.pop("PAD_KEYS", None)

    def test_embajada_sigue_en_raiz(self):
        status, body = call(despacho.application, path="/health")
        self.assertTrue(status.startswith("200"))
        self.assertIn(b"embajada", body.lower())


if __name__ == "__main__":
    unittest.main()
