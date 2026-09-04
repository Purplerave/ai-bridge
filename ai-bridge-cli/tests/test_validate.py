import json
from pathlib import Path

from ai_bridge_cli.validate import validate_file, validate_path


FIXTURES = Path(__file__).parent / "fixtures"


def test_valid_message_passes():
    valid, errs = validate_file(FIXTURES / "2026-09-04_1200_test-fixture-greeting.md")
    assert valid is True
    assert errs == []


def test_missing_from_fails():
    valid, errs = validate_file(FIXTURES / "invalid_missing_from.md")
    assert valid is False
    assert any("from" in e for e in errs)


def test_bad_date_fails():
    valid, errs = validate_file(FIXTURES / "invalid_bad_date.md")
    assert valid is False
    assert any("date" in e.lower() for e in errs)


def test_bad_filename_fails():
    valid, errs = validate_file(FIXTURES / "invalid_bad_name.md")
    assert valid is False
    assert any("Filename" in e for e in errs)


def test_validate_path_counts():
    ok, total, results = validate_path(FIXTURES)
    assert total == 4
    assert ok == 1
    assert len(results) == 3
