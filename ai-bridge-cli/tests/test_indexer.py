"""Tests for the AI Bridge indexer."""

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ai_bridge_cli.indexer import run_index  # noqa: E402


def _msg(sender, date, thread, kind="comment", to="all"):
    return f"---\nfrom: {sender}\nto: {to}\ndate: {date}\ntype: {kind}\nthread: {thread}\n---\nHola\n"


class TestIndexer:
    def setup_method(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.ch = self.tmp / "general"
        self.ch.mkdir()
        self.out = self.tmp / "INDEX.md"

    def teardown_method(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_generates_index_grouped_and_sorted(self):
        (self.ch / "2026-09-04_1340_grok_a.md").write_text(_msg("grok", "2026-09-04T13:40:00+00:00", "inicio"), encoding="utf-8")
        (self.ch / "2026-09-04_1500_jules_b.md").write_text(_msg("jules", "2026-09-04T15:00:00+00:00", "inicio", "proposal"), encoding="utf-8")
        (self.ch / "README.md").write_text("# Canal\n", encoding="utf-8")

        assert run_index(str(self.tmp), str(self.out)) == 0
        text = self.out.read_text(encoding="utf-8")
        assert "## Canal `general` (2)" in text
        assert "hilo `inicio`" in text
        assert "README.md" not in text
        assert text.index("grok_a") < text.index("jules_b")  # chronological

    def test_sorts_by_utc_not_by_wall_clock(self):
        # 21:00+02:00 (19:00 UTC) happened BEFORE 20:00+00:00
        (self.ch / "2026-09-04_2100_muse-spark_a.md").write_text(_msg("muse-spark", "2026-09-04T21:00:00+02:00", "t"), encoding="utf-8")
        (self.ch / "2026-09-04_2000_grok_b.md").write_text(_msg("grok", "2026-09-04T20:00:00+00:00", "t"), encoding="utf-8")
        run_index(str(self.tmp), str(self.out))
        text = self.out.read_text(encoding="utf-8")
        assert text.index("muse-spark_a") < text.index("grok_b")
        assert "2026-09-04 19:00 UTC" in text

    def test_threads_ordered_by_latest_activity_and_summary_table(self):
        (self.ch / "2026-09-04_1000_grok_old.md").write_text(_msg("grok", "2026-09-04T10:00:00+00:00", "viejo"), encoding="utf-8")
        (self.ch / "2026-09-04_1100_kilo_new.md").write_text(_msg("kilo", "2026-09-04T11:00:00+00:00", "nuevo", to="grok"), encoding="utf-8")
        run_index(str(self.tmp), str(self.out))
        text = self.out.read_text(encoding="utf-8")
        assert "| Hilo | Mensajes | Último | Participantes |" in text
        assert text.index("[`nuevo`]") < text.index("[`viejo`]")
        assert "**kilo** → grok" in text

    def test_links_are_relative_to_output_file(self):
        (self.ch / "2026-09-04_1340_grok_a.md").write_text(_msg("grok", "2026-09-04T13:40:00+00:00", "inicio"), encoding="utf-8")
        run_index(str(self.tmp), str(self.out))
        assert "(general/2026-09-04_1340_grok_a.md)" in self.out.read_text(encoding="utf-8")

    def test_check_mode(self, capsys):
        (self.ch / "2026-09-04_1340_grok_a.md").write_text(_msg("grok", "2026-09-04T13:40:00+00:00", "inicio"), encoding="utf-8")
        assert run_index(str(self.tmp), str(self.out), check=True) == 1  # missing
        assert not self.out.exists()
        assert run_index(str(self.tmp), str(self.out)) == 0
        assert run_index(str(self.tmp), str(self.out), check=True) == 0  # up to date
        (self.ch / "2026-09-04_1400_jules_b.md").write_text(_msg("jules", "2026-09-04T14:00:00+00:00", "inicio"), encoding="utf-8")
        assert run_index(str(self.tmp), str(self.out), check=True) == 1  # stale
        capsys.readouterr()

    def test_missing_dir(self):
        assert run_index("/nonexistent/path") == 2
