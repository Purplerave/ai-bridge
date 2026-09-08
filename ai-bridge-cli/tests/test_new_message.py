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


def test_yaml_special_values_are_quoted(tmp_path):
    # sender=null should not become YAML null
    name, content = build_message(sender="null", slug="test", body="hola", now=NOW)
    assert 'from: "null"' in content
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    r = validate_file(p, now=NOW)
    assert r.is_valid, [i.message for i in r.issues]
    assert r.frontmatter["from"] == "null"

    # to=null, thread=null, sender=yes, sender=001
    for special in ["null", "yes", "true", "001", "no"]:
        name, content = build_message(sender=special, slug="test", to=special, thread=special, body="x", now=NOW)
        p = tmp_path / name
        p.write_text(content, encoding="utf-8")
        r = validate_file(p, now=NOW)
        assert r.is_valid, f"{special} failed: {[i.message for i in r.issues]}"
        assert r.frontmatter["from"] == special


def test_body_control_chars_rejected():
    with pytest.raises(ValueError, match="control"):
        build_message(sender="grok", slug="x", body="hola\x00mundo", now=NOW)


def test_body_limit():
    long_body = "a" * 20001
    with pytest.raises(ValueError, match="exceeds"):
        build_message(sender="grok", slug="x", body=long_body, now=NOW)


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

    def test_channel_traversal_blocked(self, capsys):
        # ../outside should fail
        assert run_new(sender="grok", slug="hola", channel="../outside", root=str(self.tmp), body="x") == 2
        assert run_new(sender="grok", slug="hola", channel="general/../../etc", root=str(self.tmp), body="x") == 2
        # absolute path
        assert run_new(sender="grok", slug="hola", channel="/tmp", root=str(self.tmp), body="x") == 2
        capsys.readouterr()

    def test_channel_must_be_single_segment(self, capsys):
        assert run_new(sender="grok", slug="hola", channel="a/b", root=str(self.tmp), body="x") == 2
        assert run_new(sender="grok", slug="hola", channel="", root=str(self.tmp), body="x") == 2
        capsys.readouterr()


class TestAutoIndex:
    """`new` regenera INDEX.md del repo: el fallo recurrente de main muere."""

    def _mk_repo(self, tmp_path: Path) -> Path:
        root = tmp_path / "repo"
        (root / "channels" / "general").mkdir(parents=True)
        (root / "channels" / "general" / "README.md").write_text("# general\n")
        (root / "INDEX.md").write_text("# índice vacío\n", encoding="utf-8")
        return root

    def test_run_new_regenerates_index(self, tmp_path, capsys):
        root = self._mk_repo(tmp_path)
        code = run_new(sender="arena", slug="prueba-index", channel="general",
                       root=str(root / "channels"), body="hola")
        assert code == 0
        index = (root / "INDEX.md").read_text(encoding="utf-8")
        assert "prueba-index" in index
        assert "regenerado" in capsys.readouterr().out

    def test_run_new_no_index_flag_skips(self, tmp_path, capsys):
        root = self._mk_repo(tmp_path)
        before = (root / "INDEX.md").read_text(encoding="utf-8")
        code = run_new(sender="arena", slug="sin-index", channel="general",
                       root=str(root / "channels"), body="hola", regenerate_index=False)
        assert code == 0
        assert (root / "INDEX.md").read_text(encoding="utf-8") == before

    def test_run_new_without_repo_index_only_notifies(self, tmp_path, capsys):
        solo = tmp_path / "solo"
        (solo / "channels" / "general").mkdir(parents=True)
        (solo / "channels" / "general" / "README.md").write_text("# general\n")
        code = run_new(sender="arena", slug="sin-repo", channel="general",
                       root=str(solo / "channels"), body="hola")
        assert code == 0
        assert "INDEX.md del repo no encontrado" in capsys.readouterr().out
