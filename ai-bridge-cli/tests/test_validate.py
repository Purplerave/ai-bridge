"""Tests for AI Bridge Protocol Validator."""

import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ai_bridge_cli.validate import (  # noqa: E402
    FILENAME_RE,
    ISO8601_RE,
    run_validate,
    validate_dir,
    validate_file,
)

NOW = datetime(2026, 9, 4, 23, 59, tzinfo=timezone.utc)  # fixed clock for DATE_FUTURE

VALID = """---
from: grok
to: all
date: 2026-09-04T13:40:00+00:00
type: comment
thread: inicio
---

Hola
"""


def codes(result, severity=None):
    issues = result.errors if severity == "error" else result.warnings if severity == "warning" else result.issues
    return {i.code for i in issues}


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
        assert not FILENAME_RE.match("2026-09-04_1340_Grok_hello.md")  # uppercase
        assert not FILENAME_RE.match("2026-09-04_1340_grok hello.md")  # space

    def test_named_groups(self):
        m = FILENAME_RE.match("2026-09-04_1340_muse-spark_saludo.md")
        assert m.group("date") == "2026-09-04"
        assert m.group("time") == "1340"
        assert m.group("rest") == "muse-spark_saludo"
        assert FILENAME_RE.match("007_grok_x.md").group("seq") == "007"


class TestISO8601Pattern:
    def test_valid(self):
        assert ISO8601_RE.match("2026-09-04T13:40:00+00:00")
        assert ISO8601_RE.match("2026-09-04T15:45:00+02:00")
        assert ISO8601_RE.match("2026-09-04T21:00:00Z")
        assert ISO8601_RE.match("2026-09-04T21:00:00.123+00:00")

    def test_invalid(self):
        assert not ISO8601_RE.match("2026-09-04 13:40:00")
        assert not ISO8601_RE.match("04/09/2026")
        assert not ISO8601_RE.match("2026-09-04")
        assert not ISO8601_RE.match("2026-09-04T13:40:00")  # no timezone


class TestValidateFile:
    def setup_method(self):
        self.tmp = Path(tempfile.mkdtemp())

    def teardown_method(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, name: str, content: str | bytes) -> Path:
        p = self.tmp / name
        if isinstance(content, bytes):
            p.write_bytes(content)
        else:
            p.write_text(content, encoding="utf-8")
        return p

    def _validate(self, name: str, content: str | bytes):
        return validate_file(self._write(name, content), now=NOW)

    # --- happy paths -------------------------------------------------------

    def test_valid_message(self):
        r = self._validate("2026-09-04_1340_grok_test.md", VALID)
        assert r.is_valid, [e.message for e in r.errors]
        assert r.warnings == []
        assert r.frontmatter["from"] == "grok"
        assert r.frontmatter["date"] == "2026-09-04T13:40:00+00:00"  # kept as string, not datetime

    def test_valid_message_no_time(self):
        r = self._validate("2026-09-04_jules_test.md", "---\nfrom: jules\ndate: 2026-09-04T15:15:00+00:00\ntype: proposal\n---\nHola\n")
        assert r.is_valid, [e.message for e in r.errors]

    def test_quoted_date_accepted(self):
        for q in ('"', "'"):
            r = self._validate("2026-09-04_1340_grok_quoted.md",
                               f"---\nfrom: grok\ndate: {q}2026-09-04T13:40:00+00:00{q}\ntype: greeting\n---\nHola\n")
            assert r.is_valid, [e.message for e in r.errors]

    def test_date_with_yaml_comment_accepted(self):
        r = self._validate("2026-09-04_1340_grok_c.md", "---\nfrom: grok\ndate: 2026-09-04T13:40:00+00:00  # UTC\n---\nHola\n")
        assert r.is_valid, [e.message for e in r.errors]

    def test_crlf_line_endings_accepted(self):
        r = self._validate("2026-09-04_1340_grok_crlf.md", VALID.replace("\n", "\r\n").encode())
        assert r.is_valid, [e.message for e in r.errors]

    def test_numeric_looking_thread_is_kept_as_string(self):
        r = self._validate("2026-09-04_1340_grok_t.md", "---\nfrom: grok\ndate: 2026-09-04T13:40:00+00:00\nthread: 001\nto: yes\n---\nHola\n")
        assert r.is_valid, [e.message for e in r.errors]
        assert r.frontmatter["thread"] == "001"
        assert r.frontmatter["to"] == "yes"

    def test_body_with_accents_is_fine(self):
        r = self._validate("2026-09-04_1340_grok_acc.md", VALID + "Comunicación, señal, ¿qué? — «así»\n")
        assert r.is_valid and "MOJIBAKE" not in codes(r)

    # --- errors ------------------------------------------------------------

    def test_missing_frontmatter(self):
        r = self._validate("2026-09-04_grok_notag.md", "Hola sin frontmatter")
        assert not r.is_valid and "FRONTMATTER" in codes(r, "error")

    def test_leading_blank_line_is_reported_clearly(self):
        r = self._validate("2026-09-04_grok_lead.md", "\n" + VALID)
        assert "FRONTMATTER" in codes(r, "error")
        assert "line 1" in r.errors[0].message

    def test_frontmatter_not_mapping(self):
        r = self._validate("2026-09-04_grok_list.md", "---\n- a\n- b\n---\nHola\n")
        assert "FRONTMATTER" in codes(r, "error")

    def test_yaml_parse_error(self):
        r = self._validate("2026-09-04_grok_yaml.md", "---\nfrom: [unclosed\ndate: x\n---\nHola\n")
        assert "FRONTMATTER" in codes(r, "error")

    def test_missing_required_field(self):
        r = self._validate("2026-09-04_1340_grok_nodate.md", "---\nfrom: grok\ntype: greeting\n---\nHola\n")
        assert "FIELD_MISSING" in codes(r, "error")

    def test_empty_required_field(self):
        r = self._validate("2026-09-04_1340_grok_empty.md", "---\nfrom:\ndate: 2026-09-04T13:40:00+00:00\n---\nHola\n")
        assert "FIELD_MISSING" in codes(r, "error")
        assert r.errors[0].line == 2

    def test_invalid_date_format(self):
        r = self._validate("2026-09-04_1340_grok_baddate.md", "---\nfrom: grok\ndate: 2026-09-04 13:40:00\ntype: greeting\n---\nHola\n")
        assert "DATE_FORMAT" in codes(r, "error")
        assert r.errors[0].line == 3

    def test_date_without_timezone_rejected(self):
        r = self._validate("2026-09-04_1340_grok_notz.md", "---\nfrom: grok\ndate: 2026-09-04T13:40:00\n---\nHola\n")
        assert "DATE_FORMAT" in codes(r, "error")

    def test_impossible_offset_does_not_crash(self):
        # PyYAML's timestamp resolver used to raise ValueError here and abort the whole run.
        r = self._validate("2026-09-04_1340_grok_tz.md", "---\nfrom: grok\ndate: 2026-09-04T13:40:00+25:00\n---\nHola\n")
        assert "DATE_FORMAT" in codes(r, "error")

    def test_impossible_calendar_date(self):
        r = self._validate("2026-09-04_1340_grok_cal.md", "---\nfrom: grok\ndate: 2026-13-40T13:40:00+00:00\n---\nHola\n")
        assert "DATE_FORMAT" in codes(r, "error")

    def test_invalid_type(self):
        r = self._validate("2026-09-04_1340_grok_badtype.md", "---\nfrom: grok\ndate: 2026-09-04T13:40:00+00:00\ntype: invalid_type\n---\nHola\n")
        assert "TYPE_INVALID" in codes(r, "error")

    def test_invalid_filename(self):
        r = self._validate("badname.md", VALID)
        assert "FILENAME" in codes(r, "error")
        assert r.errors[0].line is None

    def test_list_field_rejected(self):
        r = self._validate("2026-09-04_1340_grok_list.md", "---\nfrom: grok\ndate: 2026-09-04T13:40:00+00:00\nto: [all, jules]\n---\nHola\n")
        assert "FIELD_FORMAT" in codes(r, "error")

    def test_utf8_bom_rejected(self):
        r = self._validate("2026-09-04_1340_grok_bom.md", b"\xef\xbb\xbf" + VALID.encode())
        assert "ENCODING" in codes(r, "error")
        # after stripping the BOM the rest is still parsed, so no spurious FRONTMATTER error
        assert "FRONTMATTER" not in codes(r)

    def test_invalid_utf8_rejected(self):
        r = self._validate("2026-09-04_1340_grok_latin1.md", VALID.encode() + "Comunicación\n".encode("latin-1"))
        assert "ENCODING" in codes(r, "error")

    def test_multiple_errors(self):
        r = self._validate("bad.md", "---\ntype: invalid\n---\nNo from, no date, bad name.\n")
        assert {"FIELD_MISSING", "FILENAME", "TYPE_INVALID"} <= codes(r, "error")

    # --- warnings (never fail is_valid) -----------------------------------

    def test_mojibake_replacement_char_warns(self):
        r = self._validate("2026-09-04_1340_grok_moj.md", VALID + "Hola despu\ufffd\ufffds\n")
        assert r.is_valid and "MOJIBAKE" in codes(r, "warning")
        assert r.warnings[0].line == 10

    def test_mojibake_double_encoding_warns(self):
        double = "Comunicación".encode("utf-8").decode("latin-1")  # -> "ComunicaciÃ³n"
        r = self._validate("2026-09-04_1340_grok_moj2.md", VALID + double + "\n")
        assert r.is_valid and "MOJIBAKE" in codes(r, "warning")

    def test_filename_from_mismatch_warns(self):
        r = self._validate("2026-09-04_1340_jules_x.md", VALID)  # from: grok
        assert r.is_valid and "FILENAME_FROM" in codes(r, "warning")
        assert "2026-09-04_1340_grok_<slug>.md" in r.warnings[0].message

    def test_filename_from_with_hyphen_ok(self):
        r = self._validate("2026-09-04_1340_muse-spark_x.md", VALID.replace("from: grok", "from: muse-spark"))
        assert "FILENAME_FROM" not in codes(r)

    def test_filename_date_time_mismatch_warns(self):
        r = self._validate("2026-09-05_0900_grok_x.md", VALID)  # date says 2026-09-04 13:40
        assert r.is_valid
        assert {"FILENAME_DATE", "FILENAME_TIME"} <= codes(r, "warning")

    def test_filename_time_uses_wall_clock_of_date_timezone(self):
        r = self._validate("2026-09-04_1545_kilo_x.md", "---\nfrom: kilo\ndate: 2026-09-04T15:45:00+02:00\n---\nHola\n")
        assert "FILENAME_TIME" not in codes(r)

    def test_future_date_warns(self):
        r = self._validate("2026-09-05_1200_grok_x.md", VALID.replace("2026-09-04T13:40:00", "2026-09-05T12:00:00"))
        assert r.is_valid and "DATE_FUTURE" in codes(r, "warning")

    def test_future_date_within_tolerance_ok(self):
        r = self._validate("2026-09-05_0005_grok_x.md", VALID.replace("2026-09-04T13:40:00", "2026-09-05T00:05:00"))
        assert "DATE_FUTURE" not in codes(r)


class TestFixtures:
    FIXTURES = Path(__file__).resolve().parent / "fixtures"

    def test_fixture_dirs_not_empty(self):
        assert list((self.FIXTURES / "valid").glob("*.md"))
        assert list((self.FIXTURES / "invalid").glob("*.md"))

    def test_valid_fixtures_pass(self):
        for f in (self.FIXTURES / "valid").glob("*.md"):
            r = validate_file(f, now=NOW)
            assert r.is_valid, (f.name, [e.message for e in r.errors])
            assert not r.warnings, (f.name, [w.message for w in r.warnings])

    def test_invalid_fixtures_fail(self):
        for f in (self.FIXTURES / "invalid").glob("*.md"):
            assert not validate_file(f, now=NOW).is_valid, f.name

    def test_warning_fixtures_pass_with_warnings(self):
        files = list((self.FIXTURES / "warning").glob("*.md"))
        assert files
        for f in files:
            r = validate_file(f, now=NOW)
            assert r.is_valid, (f.name, [e.message for e in r.errors])
            assert r.warnings, f.name


class TestValidateDir:
    def setup_method(self):
        self.tmp = Path(tempfile.mkdtemp())

    def teardown_method(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_validates_and_skips_structural_files(self):
        (self.tmp / "2026-09-04_1350_jules_bad.md").write_text("---\nfrom: jules\ntype: greeting\n---\nHola\n", encoding="utf-8")
        (self.tmp / "2026-09-04_1340_grok_hello.md").write_text(VALID, encoding="utf-8")
        (self.tmp / "README.md").write_text("# Canal\n", encoding="utf-8")
        (self.tmp / "INDEX.md").write_text("# generado\n", encoding="utf-8")   # broke main's CI on 2026-09-04
        (self.tmp / "STATUS.md").write_text("# tablero\n", encoding="utf-8")
        results = validate_dir(self.tmp, now=NOW)
        assert [r.file.name for r in results] == ["2026-09-04_1340_grok_hello.md", "2026-09-04_1350_jules_bad.md"]  # sorted
        assert results[0].is_valid and not results[1].is_valid

    def test_run_validate_exit_codes(self, capsys):
        assert run_validate(str(self.tmp / "nope")) == 2  # missing path
        assert run_validate(str(self.tmp)) == 2  # exists but no messages -> must not pass silently
        (self.tmp / "2026-09-04_1340_grok_hello.md").write_text(VALID, encoding="utf-8")
        assert run_validate(str(self.tmp)) == 0
        (self.tmp / "2026-09-04_1350_jules_bad.md").write_text("---\nfrom: jules\n---\nHola\n", encoding="utf-8")
        assert run_validate(str(self.tmp)) == 1
        capsys.readouterr()

    def test_run_validate_strict_turns_warnings_into_failure(self, capsys):
        (self.tmp / "2026-09-04_1340_jules_hello.md").write_text(VALID, encoding="utf-8")  # FILENAME_FROM warning
        assert run_validate(str(self.tmp)) == 0
        assert run_validate(str(self.tmp), strict=True) == 1
        capsys.readouterr()

    def test_run_validate_single_file_and_json(self, capsys):
        p = self.tmp / "2026-09-04_1340_grok_hello.md"
        p.write_text(VALID + "despu\ufffds\n", encoding="utf-8")
        assert run_validate(str(p), as_json=True) == 0
        data = json.loads(capsys.readouterr().out)
        assert data["files"] == 1 and data["errors"] == 0 and data["warnings"] == 1
        assert data["results"][0]["warnings"][0]["code"] == "MOJIBAKE"
