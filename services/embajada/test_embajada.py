"""Tests unitarios Embajada (stdlib unittest + tempfile)."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

# Import desde el mismo directorio
import sys

SYS_DIR = Path(__file__).resolve().parent
if str(SYS_DIR) not in sys.path:
    sys.path.insert(0, str(SYS_DIR))

import app  # noqa: E402


class NormalizeTests(unittest.TestCase):
    def test_json_body(self):
        raw = json.dumps(
            {"from": "grok", "type": "comment", "thread": "t", "body": "hola"}
        ).encode()
        rec = app.normalize_payload(raw, "application/json")
        self.assertEqual(rec["from"], "grok")
        self.assertEqual(rec["body"], "hola")
        self.assertEqual(rec["via"], "embajada")
        self.assertTrue(rec["id"])

    def test_plain_text(self):
        rec = app.normalize_payload(b"solo texto", "text/plain")
        self.assertEqual(rec["body"], "solo texto")
        self.assertEqual(rec["from"], "anonymous")

    def test_ids_unicos_mismo_emisor_mismo_segundo(self):
        # Hallazgo Arena (review Embajada 0.2): dos POST del mismo emisor en el
        # mismo segundo colisionaban. El id lleva microsegundos + azar.
        raws = [
            json.dumps({"from": "grok", "body": f"m{i}"}).encode()
            for i in range(50)
        ]
        ids = {
            app.normalize_payload(r, "application/json")["id"] for r in raws
        }
        self.assertEqual(len(ids), 50)

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            app.normalize_payload(b"  ", "text/plain")


class StoreTests(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "messages.jsonl"
            rec = app.normalize_payload(
                b'{"from":"a","body":"x"}', "application/json"
            )
            app.append_msg(rec, store=store)
            rows = app.read_msgs(store=store)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["body"], "x")


class TokenTests(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("EMBAJADA_TOKEN", None)

    def test_no_token_open(self):
        os.environ.pop("EMBAJADA_TOKEN", None)
        self.assertTrue(app.token_ok({}))

    def test_bearer_ok(self):
        os.environ["EMBAJADA_TOKEN"] = "secreto"
        self.assertTrue(app.token_ok({"Authorization": "Bearer secreto"}))

    def test_header_alt_ok(self):
        os.environ["EMBAJADA_TOKEN"] = "secreto"
        self.assertTrue(app.token_ok({"X-Embajada-Token": "secreto"}))

    def test_wrong_rejected(self):
        os.environ["EMBAJADA_TOKEN"] = "secreto"
        self.assertFalse(app.token_ok({"Authorization": "Bearer otro"}))


class BridgeTests(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("EMBAJADA_BRIDGE", None)
        os.environ.pop("EMBAJADA_TOKEN", None)

    def test_bridge_off_por_defecto(self):
        os.environ.pop("EMBAJADA_BRIDGE", None)
        self.assertFalse(app.bridge_enabled())

    def test_bridge_on_con_flag(self):
        os.environ["EMBAJADA_BRIDGE"] = "1"
        self.assertTrue(app.bridge_enabled())

    def test_bridge_write_genera_md_valido(self):
        import datetime as _dt
        with tempfile.TemporaryDirectory() as tmp:
            general = Path(tmp) / "general"
            general.mkdir()
            rec = {
                "from": "grok",
                "type": "comment",
                "thread": "t",
                "body": "Hola puente desde embajada",
                "date": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            }
            dest = app.bridge_write(rec, channels_dir=general)
            self.assertTrue(dest.is_file())
            self.assertRegex(dest.name, r"^\d{4}-\d{2}-\d{2}_\d{4}_grok_hola-puente-desde-embajada\.md$")
            text = dest.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---\nfrom: grok\n"))


if __name__ == "__main__":
    unittest.main()
