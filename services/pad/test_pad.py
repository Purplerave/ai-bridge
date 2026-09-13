"""Tests pad compartido (stdlib unittest)."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

SYS_DIR = Path(__file__).resolve().parent
if str(SYS_DIR) not in sys.path:
    sys.path.insert(0, str(SYS_DIR))

os.environ["PAD_DATA_DIR"] = tempfile.mkdtemp()

import pad as padmod  # noqa: E402


class PadTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop("PAD_KEYS", None)
        for f in Path(os.environ["PAD_DATA_DIR"]).glob("*.md"):
            f.unlink()

    def test_append_y_read(self):
        padmod.append_pad("demo1", "hola")
        self.assertEqual(padmod.read_pad("demo1"), "hola\n")
        padmod.append_pad("demo1", "mundo")
        self.assertIn("mundo", padmod.read_pad("demo1"))

    def test_read_inexistente_vacio(self):
        self.assertEqual(padmod.read_pad("noexiste99"), "")

    def test_id_invalido(self):
        with self.assertRaises(ValueError):
            padmod.append_pad("../fuera", "x")

    def test_key_abierto_sin_config(self):
        self.assertTrue(padmod.key_ok("libre1", {}))

    def test_key_cerrado(self):
        os.environ["PAD_KEYS"] = "priv1:secreto"
        self.assertFalse(padmod.key_ok("priv1", {}))
        self.assertTrue(padmod.key_ok("priv1", {"X-Pad-Key": "secreto"}))
        self.assertFalse(padmod.key_ok("priv1", {"X-Pad-Key": "otra"}))

    def test_limite_tamano(self):
        with self.assertRaises(ValueError):
            padmod.append_pad("gordo", "x" * (padmod.MAX_PAD + 1))


if __name__ == "__main__":
    unittest.main()
