"""Tests for `ai-bridge-cli new`."""

import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ai_bridge_cli.cli import main  # noqa: E402
from ai_bridge_cli.new_message import build_message, run_new, slugify  # noqa: E402
from ai_bridge_cli.validate import validate_file  # noqa: E402

NOW = datetime(2026, 9, 4, 16, 27, 5, tzinfo=timezone.utc)


def test_slugify():
    assert slugify("Muse Spark") == "muse-spark"
    assert slugify("Revisión + mejoras: CLI!") == "revision-mejoras-cli"
    assert slugify("  ---  ") == "mensaje"


def test_build_message_is_protocol_compliant(tmp_path):
    name, content = build_message(sender="Muse Spark", slug="Respuesta al linter", thread="linter-kickoff",
                                  msg_type="status", body="Hola\n", now=NOW)
    assert name == "2026-09-04_1627_muse-spark_respuesta-al-linter.md"
    assert "date: 2026-09-04T16:27:05+00:00" in content
    assert "from: muse-spark" in content
    assert "thread: linter-kickoff" in content
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    r = validate_file(p, now=NOW)
    assert r.is_valid and not r.warnings, [i.message for i in r.issues]


def test_build_message_rejects_bad_type():
    with pytest.raises(ValueError):
        build_message(sender="grok", slug="x", msg_type="rant", now=NOW)


class TestRunNew:
    def setup_method(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "general").mkdir()

    def teardown_method(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_writes_valid_file(self, capsys):
        rc = run_new(sender="grok", slug="hola", root=str(self.tmp), body="Hola a todos\n")
        assert rc == 0
        files = list((self.tmp / "general").glob("*.md"))
        assert len(files) == 1
        assert validate_file(files[0]).is_valid
        assert "Hola a todos" in files[0].read_text(encoding="utf-8")
        capsys.readouterr()

    def test_missing_channel_fails(self, capsys):
        assert run_new(sender="grok", slug="hola", channel="nope", root=str(self.tmp), body="x") == 2
        capsys.readouterr()

    def test_dry_run_writes_nothing(self, capsys):
        assert main(["new", "--from", "grok", "--slug", "hola", "--root", str(self.tmp), "--body", "x", "--dry-run"]) == 0
        assert list((self.tmp / "general").glob("*.md")) == []
        out = capsys.readouterr().out
        assert "from: grok" in out and "---" in out
