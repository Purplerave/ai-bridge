"""Tests serve.py (servidor real en puerto efímero)."""

from __future__ import annotations

import os
import socket
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path

SYS_DIR = Path(__file__).resolve().parent
for p in (str(SYS_DIR), str(SYS_DIR.parent / "pad"), str(SYS_DIR.parent / "embajada")):
    if p not in sys.path:
        sys.path.insert(0, p)

import serve as servemod  # noqa: E402


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def call(base: str, path: str, method="GET", body: bytes | None = None, headers=None):
    r = urllib.request.Request(
        base + path, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


class ServeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        os.environ["PAD_DATA_DIR"] = cls.tmp
        os.environ["PAD_KEYS"] = "t1:c1"
        cls.port = free_port()
        from http.server import ThreadingHTTPServer
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", cls.port), servemod.Handler)
        cls.th = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.th.start()
        time.sleep(0.5)
        cls.base = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        os.environ.pop("PAD_KEYS", None)

    def test_embajada_en_raiz(self):
        code, body = call(self.base, "/health")
        self.assertEqual(code, 200)
        self.assertIn(b"embajada", body)

    def test_pad_bajo_prefijo(self):
        code, _ = call(self.base, "/pad/api/t1", method="POST",
                       body="hola serve".encode(),
                       headers={"X-Pad-Key": "c1", "Content-Type": "text/plain"})
        self.assertEqual(code, 200)
        code, body = call(self.base, "/pad/api/t1")
        self.assertEqual(code, 200)
        self.assertIn(b"hola serve", body)

    def test_pad_key_mala_403(self):
        code, _ = call(self.base, "/pad/api/t1", method="POST",
                       body=b"x", headers={"X-Pad-Key": "mala"})
        self.assertEqual(code, 403)


if __name__ == "__main__":
    unittest.main()
