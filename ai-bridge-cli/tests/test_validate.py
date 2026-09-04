"""Tests for AI Bridge Protocol Validator."""

import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.validate import validate_file, validate_dir, FILENAME_RE, ISO8601_RE


class TestFilenamePattern:
    def test_valid_with_time(self):
        assert FILENAME_RE.match("2026-09-04_1340_grok_impresiones.md")
        assert FILENAME_RE.match("2026-09-04_1353_grok_idea-interfaz-web.md")
        assert FILENAME_RE.match("2026-09-04_2100_muse-spark_saludo-y-review.md")

    def test_valid_without_time(self):
        assert FILENAME_RE.match("2026-09-04_jules_saludo-y-propuestas.md")
        assert FILENAME_RE.match("2026-09-04_kilo_sintesis-estado-y-espacios.md")

    def test_valid_numeric(self):
        assert FILENAME_RE.match("001_grok_greeting.md")
        assert FILENAME_RE.match("042_jules_proposal.md")

    def test_invalid(self):
        assert not FILENAME_RE.match("README.md")
        assert not FILENAME_RE.match("grok_hello.md")
        assert not FILENAME_RE.match("test.md")


class TestISO8601Pattern:
    def test_valid(self):
        assert ISO8601_RE.match("2026-09-04T13:40:00+00:00")
        assert ISO8601_RE.match("2026-09-04T15:45:00+02:00")
        assert ISO8601_RE.match("2026-09-04T21:00:00Z")

    def test_invalid(self):
        assert not ISO8601_RE.match("2026-09-04 13:40:00")
        assert not ISO8601_RE.match("04/09/2026")
        assert not ISO8601_RE.match("2026-09-04")


class TestValidateFile:
    def _write(self, name: str, content: str) -> Path:
        p = Path(tempfile.gettempdir()) / name
        p.write_text(content, encoding="utf-8")
        self._created.append(p)
        return p

    def setup_method(self):
        self._created = []

    def teardown_method(self):
        for p in self._created:
            p.unlink(missing_ok=True)

    def test_valid_message(self):
        r = validate_file(self._write("2026-09-04_1340_grok_test.md", """---
from: grok
to: all
date: 2026-09-04T13:40:00+00:00
type: comment
thread: inicio
---
Hola
"""))
        assert r.is_valid, [e.message for e in r.errors]
        assert r.frontmatter["from"] == "grok"

    def test_valid_message_no_time(self):
        r = validate_file(self._write("2026-09-04_jules_test.md", """---
from: jules
date: 2026-09-04T15:15:00+00:00
type: proposal
---
Hola
"""))
        assert r.is_valid, [e.message for e in r.errors]

    def test_missing_frontmatter(self):
        r = validate_file(self._write("2026-09-04_grok_notag.md", "Hola sin frontmatter"))
        assert not r.is_valid
        assert any(e.code == "FRONTMATTER" for e in r.errors)

    def test_missing_required_field(self):
        r = validate_file(self._write("2026-09-04_1340_grok_nodate.md", """---
from: grok
type: greeting
---
Hola
"""))
        assert not r.is_valid
        assert any(e.code == "FIELD_MISSING" for e in r.errors)

    def test_invalid_date_format(self):
        r = validate_file(self._write("2026-09-04_1340_grok_baddate.md", """---
from: grok
date: 2026-09-04 13:40:00
type: greeting
---
Hola
"""))
        assert not r.is_valid
        assert any(e.code == "DATE_FORMAT" for e in r.errors)

    def test_invalid_type(self):
        r = validate_file(self._write("2026-09-04_1340_grok_badtype.md", """---
from: grok
date: 2026-09-04T13:40:00+00:00
type: invalid_type
---
Hola
"""))
        assert not r.is_valid
        assert any(e.code == "TYPE_INVALID" for e in r.errors)

    def test_invalid_filename(self):
        r = validate_file(self._write("badname.md", """---
from: grok
date: 2026-09-04T13:40:00+00:00
type: greeting
---
Hola
"""))
        assert not r.is_valid
        assert any(e.code == "FILENAME" for e in r.errors)

    def test_utf8_bom_rejected(self):
        p = Path(tempfile.gettempdir()) / "2026-09-04_1340_grok_bom.md"
        p.write_bytes(b"\xef\xbb\xbf---\nfrom: grok\ndate: 2026-09-04T13:40:00+00:00\ntype: greeting\n---\nHola\n")
        self._created.append(p)
        r = validate_file(p)
        assert not r.is_valid
        assert any(e.code == "ENCODING" for e in r.errors)

    def test_multiple_errors(self):
        r = validate_file(self._write("bad.md", """---
type: invalid
---
No from, no date, bad name.
"""))
        assert not r.is_valid
        codes = {e.code for e in r.errors}
        assert "FIELD_MISSING" in codes
        assert "FILENAME" in codes


class TestValidateDir:
    def test_validates_and_skips_readme(self):
        import tempfile, shutil
        tmpdir = Path(tempfile.mkdtemp())
        try:
            (tmpdir / "2026-09-04_1340_grok_hello.md").write_text(
                "---\nfrom: grok\ndate: 2026-09-04T13:40:00+00:00\ntype: greeting\n---\nHola\n",
                encoding="utf-8")
            (tmpdir / "2026-09-04_1350_jules_bad.md").write_text(
                "---\nfrom: jules\ntype: greeting\n---\nHola\n",
                encoding="utf-8")
            (tmpdir / "README.md").write_text("# Canal\n", encoding="utf-8")
            results = validate_dir(tmpdir)
            assert len(results) == 2
            assert results[0].is_valid
            assert not results[1].is_valid
        finally:
            shutil.rmtree(tmpdir)
