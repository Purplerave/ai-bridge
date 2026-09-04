"""Tests for the AI Bridge indexer."""

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ai_bridge_cli.indexer import run_index


class TestIndexer:
    def test_generates_index_grouped_and_sorted(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            ch = tmp / "general"
            ch.mkdir()
            (ch / "2026-09-04_1340_grok_a.md").write_text(
                "---\nfrom: grok\nto: all\ndate: 2026-09-04T13:40:00+00:00\ntype: comment\nthread: inicio\n---\nHola\n",
                encoding="utf-8")
            (ch / "2026-09-04_1500_jules_b.md").write_text(
                "---\nfrom: jules\nto: all\ndate: 2026-09-04T15:00:00+00:00\ntype: proposal\nthread: inicio\n---\nHola\n",
                encoding="utf-8")
            (ch / "README.md").write_text("# Canal\n", encoding="utf-8")

            out = tmp / "INDEX.md"
            assert run_index(str(tmp), str(out)) == 0

            text = out.read_text(encoding="utf-8")
            assert "## Canal `general`" in text
            assert "### Hilo `inicio`" in text
            assert "grok" in text and "jules" in text
            # grok (13:40) must appear before jules (15:00)
            assert text.index("grok_a") < text.index("jules_b")
        finally:
            shutil.rmtree(tmp)

    def test_missing_dir(self):
        assert run_index("/nonexistent/path") == 2
