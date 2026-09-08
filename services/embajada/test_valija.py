"""Tests de la Valija (stdlib unittest + tempfile).

No tocan la red: la fuente HTTP se prueba con un archivo local, que es
exactamente el mismo camino de código tras `fetch_source`.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import valija  # noqa: E402


def msg(**kw) -> dict:
    base = {
        "id": "20260908T100000_grok",
        "from": "grok",
        "type": "comment",
        "thread": "",
        "body": "Hola desde la embajada",
        "date": "2026-09-08T10:00:00+00:00",
        "via": "embajada",
    }
    base.update(kw)
    return base


class FetchTests(unittest.TestCase):
    def test_reads_jsonl(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "messages.jsonl"
            p.write_text(
                json.dumps(msg()) + "\n" + json.dumps(msg(id="b")) + "\n",
                encoding="utf-8",
            )
            rows = valija.fetch_source(str(p))
        self.assertEqual(len(rows), 2)

    def test_skips_broken_lines(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "m.jsonl"
            p.write_text(json.dumps(msg()) + "\n{roto\n", encoding="utf-8")
            self.assertEqual(len(valija.fetch_source(str(p))), 1)

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            valija.fetch_source("/no/existe.jsonl")

    def test_coerce_messages_envelope(self):
        self.assertEqual(valija._coerce_list({"messages": [msg()]})[0]["from"], "grok")

    def test_coerce_rejects_garbage(self):
        with self.assertRaises(ValueError):
            valija._coerce_list("no")


class ConvertTests(unittest.TestCase):
    def test_produces_valid_frontmatter(self):
        out = valija.convert(msg())
        self.assertTrue(out["content"].startswith("---\n"))
        self.assertIn("from: grok", out["content"])
        self.assertIn("date: 2026-09-08T10:00:00+00:00", out["content"])
        self.assertTrue(out["filename"].startswith("2026-09-08_1000_grok_"))

    def test_unknown_type_falls_back_to_comment(self):
        out = valija.convert(msg(type="chisme"))
        self.assertIn("type: comment", out["content"])

    def test_known_type_preserved(self):
        self.assertIn("type: review", valija.convert(msg(type="review"))["content"])

    def test_provenance_note_present(self):
        self.assertIn("valija", valija.convert(msg())["content"])
        self.assertIn("declarativo", valija.convert(msg())["content"])

    def test_empty_body_rejected(self):
        with self.assertRaises(ValueError):
            valija.convert(msg(body="   "))

    def test_control_chars_rejected(self):
        with self.assertRaises(ValueError):
            valija.convert(msg(body="hola\x07mundo"))

    def test_huge_body_rejected(self):
        with self.assertRaises(ValueError):
            valija.convert(msg(body="x" * 25000))

    def test_channel_from_message_when_allowed(self):
        self.assertEqual(valija.convert(msg(channel="projects"))["channel"], "projects")

    def test_channel_falls_back_when_invalid(self):
        self.assertEqual(valija.convert(msg(channel="../etc"))["channel"], "open")

    def test_slug_from_body_when_no_subject(self):
        out = valija.convert(msg(body="# Propuesta de faro urbano\n\ntexto"))
        self.assertIn("propuesta-de-faro-urbano", out["filename"])

    def test_sender_is_slugified(self):
        out = valija.convert(msg(**{"from": "Muse Spark"}))
        self.assertIn("from: muse-spark", out["content"])

    def test_bad_date_still_converts(self):
        self.assertTrue(valija.convert(msg(date="ayer"))["filename"].endswith(".md"))

    def test_id_is_stable_hash_without_id(self):
        row = msg()
        row.pop("id")
        self.assertEqual(valija.message_id(row), valija.message_id(dict(row)))
        self.assertTrue(valija.message_id(row).startswith("sha256:"))


class PlanTests(unittest.TestCase):
    def test_new_messages_are_planned(self):
        result = valija.plan([msg()], {"delivered": {}})
        self.assertEqual(len(result["new"]), 1)

    def test_already_delivered_is_skipped(self):
        ledger = {"delivered": {"20260908T100000_grok": {"path": "x"}}}
        result = valija.plan([msg()], ledger)
        self.assertEqual(result["new"], [])
        self.assertEqual(len(result["skipped"]), 1)

    def test_duplicate_in_same_batch_only_once(self):
        result = valija.plan([msg(), msg()], {"delivered": {}})
        self.assertEqual(len(result["new"]), 1)

    def test_rejected_are_reported_not_raised(self):
        result = valija.plan([msg(body="")], {"delivered": {}})
        self.assertEqual(len(result["rejected"]), 1)
        self.assertIn("body", result["rejected"][0]["error"])


class DeliverTests(unittest.TestCase):
    def test_writes_into_channel(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            written = valija.deliver([valija.convert(msg())], root)
            path = root / written[0]["path"]
            self.assertTrue(path.is_file())
            self.assertIn("channels/open/", written[0]["path"].replace("\\", "/"))

    def test_never_overwrites(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            item = valija.convert(msg())
            valija.deliver([item], root)
            second = valija.deliver([dict(item)], root)
            self.assertIn("-2.md", second[0]["path"])


class LedgerTests(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "state" / "ledger.json"
            ledger = {"version": 1, "delivered": {"a": {"path": "x"}}}
            valija.save_ledger(p, ledger)
            self.assertEqual(valija.load_ledger(p)["delivered"]["a"]["path"], "x")

    def test_corrupt_ledger_starts_clean(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "l.json"
            p.write_text("{roto", encoding="utf-8")
            self.assertEqual(valija.load_ledger(p)["delivered"], {})

    def test_missing_ledger_starts_clean(self):
        self.assertEqual(valija.load_ledger(Path("/no/hay.json"))["delivered"], {})


class EndToEndTests(unittest.TestCase):
    def test_run_twice_is_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src = root / "messages.jsonl"
            src.write_text(json.dumps(msg()) + "\n", encoding="utf-8")
            ledger = root / "state" / "valija-ledger.json"
            args = ["--source", str(src), "--root", str(root), "--ledger", str(ledger)]

            self.assertEqual(valija.main(args), 0)
            first = list((root / "channels" / "open").glob("*.md"))
            self.assertEqual(len(first), 1)

            self.assertEqual(valija.main(args), 0)
            self.assertEqual(len(list((root / "channels" / "open").glob("*.md"))), 1)

    def test_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src = root / "m.jsonl"
            src.write_text(json.dumps(msg()) + "\n", encoding="utf-8")
            valija.main(["--source", str(src), "--root", str(root), "--dry-run"])
            self.assertFalse((root / "channels").exists())

    def test_unreachable_source_returns_1(self):
        self.assertEqual(valija.main(["--source", "/no/existe.jsonl", "--dry-run"]), 1)


class BridgeValidatorTests(unittest.TestCase):
    """Lo que produce la valija debe pasar el validador real del Puente."""

    def test_output_passes_ai_bridge_cli_validate(self):
        repo = Path(__file__).resolve().parents[2]
        sys.path.insert(0, str(repo / "ai-bridge-cli"))
        from ai_bridge_cli.validate import validate_file

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            written = valija.deliver(
                [
                    valija.convert(msg()),
                    valija.convert(msg(id="b", type="review", thread="obra-comun")),
                    valija.convert(msg(id="c", **{"from": "Muse Spark"})),
                ],
                root,
            )
            for item in written:
                result = validate_file(root / item["path"])
                self.assertEqual(result.errors, [], f"{item['path']}: {result.errors}")


if __name__ == "__main__":
    unittest.main()
