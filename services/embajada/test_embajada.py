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


class RoutingHintsTests(unittest.TestCase):
    """0.4.0: la Embajada conserva las pistas que necesita la valija."""

    def test_subject_channel_to_preserved(self):
        raw = json.dumps({
            "from": "arena", "body": "hola",
            "to": "grok", "subject": "faro urbano", "channel": "projects",
        }).encode()
        rec = app.normalize_payload(raw, "application/json")
        self.assertEqual(rec["subject"], "faro urbano")
        self.assertEqual(rec["channel"], "projects")
        self.assertEqual(rec["to"], "grok")

    def test_defaults_when_absent(self):
        rec = app.normalize_payload(b'{"from":"x","body":"y"}', "application/json")
        self.assertEqual(rec["to"], "all")
        self.assertNotIn("subject", rec)
        self.assertNotIn("channel", rec)

    def test_slug_alias_for_subject(self):
        rec = app.normalize_payload(b'{"body":"y","slug":"mi-tema"}', "application/json")
        self.assertEqual(rec["subject"], "mi-tema")

    def test_channel_lowercased(self):
        rec = app.normalize_payload(b'{"body":"y","channel":"OPEN"}', "application/json")
        self.assertEqual(rec["channel"], "open")


class IdentityTests(unittest.TestCase):
    """0.5.0 — criterio 3 del issue #17: ids únicos, dedup y rechazo explícito."""

    def test_ids_unique_same_sender_same_second(self):
        """La colisión real del 07-09: mismo emisor, mismo segundo, ids distintos."""
        raw = b'{"from":"rapid","body":"uno"}'
        ids = {app.normalize_payload(raw, "application/json")["id"] for _ in range(50)}
        self.assertEqual(len(ids), 50)

    def test_client_id_respected(self):
        rec = app.normalize_payload(
            b'{"from":"a","body":"x","id":"mi-id-001"}', "application/json"
        )
        self.assertEqual(rec["id"], "mi-id-001")

    def test_client_id_invalid_rejected(self):
        with self.assertRaises(ValueError):
            app.normalize_payload(
                b'{"from":"a","body":"x","id":"mal id con espacios"}', "application/json"
            )

    def test_state_recibido(self):
        rec = app.normalize_payload(b'{"from":"a","body":"x"}', "application/json")
        self.assertEqual(rec["state"], "recibido")

    def test_dedup_same_content_200(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "messages.jsonl"
            payload = b'{"from":"a","body":"hola","id":"abc-1"}'
            code1, out1 = app.process_message(payload, "application/json", store=store)
            code2, out2 = app.process_message(payload, "application/json", store=store)
            self.assertEqual(code1, 201)
            self.assertEqual(code2, 200)
            self.assertTrue(out2["dedup"])
            self.assertEqual(len(app.read_msgs(store=store)), 1)

    def test_same_id_different_body_409(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "messages.jsonl"
            code1, _ = app.process_message(
                b'{"from":"a","body":"uno","id":"abc-1"}', "application/json", store=store
            )
            code2, out2 = app.process_message(
                b'{"from":"a","body":"dos","id":"abc-1"}', "application/json", store=store
            )
            self.assertEqual(code1, 201)
            self.assertEqual(code2, 409)
            self.assertFalse(out2["ok"])
            self.assertEqual(len(app.read_msgs(store=store)), 1)

    def test_dedup_ignores_arrival_metadata(self):
        """Mismo contenido reenviado más tarde: dedup aunque cambie date/via."""
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "messages.jsonl"
            first = b'{"from":"a","body":"hola","id":"abc-1"}'
            second = b'{"from":"a","body":"hola","id":"abc-1","type":"comment"}'
            code1, _ = app.process_message(first, "application/json", store=store)
            code2, out2 = app.process_message(second, "application/json", store=store)
            self.assertEqual(code1, 201)
            self.assertEqual(code2, 200)
            self.assertTrue(out2["dedup"])

    def test_wsgi_and_app_share_process_message(self):
        """WSGI y HTTP no pueden divergir: ambos pasan por process_message."""
        import wsgi

        self.assertIs(wsgi.emb.process_message, app.process_message)


if __name__ == "__main__":
    unittest.main()
