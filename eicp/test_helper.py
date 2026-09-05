"""Tests for eicp/helper.py — run: pytest eicp/test_helper.py -q"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from helper import (
    EICP_VERSION,
    build_message,
    embed_markdown,
    main,
    parse_markdown,
    path_derived_id,
    read_state_slot,
    slot_path,
    write_state_slot,
)

# The bridge validator is the other half of this repo: an EICP message is also
# an AI Bridge message, so it has to pass both. Imported by path because the two
# packages are not installed in CI.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ai-bridge-cli"))
from ai_bridge_cli.validate import validate_file  # noqa: E402

NOW = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)


def test_build_and_roundtrip(tmp_path: Path):
    msg = build_message(
        sender="grok",
        msg_type="status",
        body="ping",
        thread="eicp-spec",
        to="all",
    )
    assert msg["eicp"] == "0.1"
    assert msg["from"] == "grok"
    assert "id" in msg

    md = embed_markdown(msg)
    assert "eicp:" in md or "eicp: " in md
    assert "eicp_id" in md
    assert "```json" in md

    path = tmp_path / "channels" / "general" / "2026-09-05_1200_grok_test.md"
    path.parent.mkdir(parents=True)
    path.write_text(md, encoding="utf-8")

    parsed = parse_markdown(md, relative_path=str(path.relative_to(tmp_path)))
    assert parsed["id"] == msg["id"]
    assert parsed["from"] == "grok"
    assert parsed["thread"] == "eicp-spec"
    assert "ping" in parsed["body"] or parsed["body"] == "ping"


def test_path_derived_id_stable():
    a = path_derived_id("channels/general/foo.md")
    b = path_derived_id("channels/general/foo.md")
    assert a == b
    assert a.startswith("path_")


def test_slot_path_and_write(tmp_path: Path):
    p = write_state_slot("project.eicp.status", "ok", root=tmp_path / "state")
    assert p.name == "project_eicp_status.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["value"] == "ok"
    assert slot_path("project.eicp.status", tmp_path / "state") == p


def test_invalid_type():
    with pytest.raises(ValueError):
        build_message(sender="grok", msg_type="nope", body="x")


# --- regressions found in the 2026-09-05 review -----------------------------


def test_handwritten_unquoted_date_stays_iso8601():
    md = ("---\neicp: 0.1\neicp_id: abc\nfrom: grok\n"
          "date: 2026-09-05T12:00:00+00:00\ntype: status\n---\n\nhola\n")
    # PyYAML loads an unquoted timestamp as a `datetime`; str() used to render
    # it with a space separator, which is not ISO 8601 and breaks the canonical
    # order of EICP 0.1.1 §3 (' ' sorts before 'T').
    assert parse_markdown(md)["date"] == "2026-09-05T12:00:00+00:00"


def test_embed_parse_roundtrip_keeps_date():
    msg = build_message(sender="grok", msg_type="status", body="ping",
                        date="2026-09-05T12:00:00+00:00")
    assert parse_markdown(embed_markdown(msg))["date"] == msg["date"]


def test_empty_eicp_field_falls_back_to_version():
    md = "---\neicp:\neicp_id: abc\nfrom: grok\ndate: 2026-09-05T12:00:00+00:00\n---\n\nhola\n"
    assert parse_markdown(md)["eicp"] == EICP_VERSION  # used to be the string "None"


def test_missing_required_frontmatter_raises_value_error():
    # Used to raise KeyError('from') / KeyError('date').
    with pytest.raises(ValueError, match="from"):
        parse_markdown("---\neicp: 0.1\neicp_id: abc\ndate: 2026-09-05T12:00:00+00:00\n---\n\nhola\n")
    with pytest.raises(ValueError, match="date"):
        parse_markdown("---\neicp: 0.1\neicp_id: abc\nfrom: grok\n---\n\nhola\n")


def test_to_must_be_a_string():
    # EICP 0.1.1 §4: `to` is a single string; it used to be silently rewritten
    # to "all" by to_frontmatter, dropping the addressing information.
    with pytest.raises(ValueError, match="mentions"):
        build_message(sender="grok", msg_type="status", body="x", to=["arena", "jules"])


def test_read_state_slot_roundtrip(tmp_path: Path):
    root = tmp_path / "state"
    assert read_state_slot("project.eicp.status", root) is None
    write_state_slot("project.eicp.status", {"owner": "grok"}, root=root)
    assert read_state_slot("project.eicp.status", root) == {"owner": "grok"}


def test_read_state_slot_tolerates_a_foreign_json_file(tmp_path: Path):
    # A JSON file that is not a slot envelope must not raise AttributeError.
    root = tmp_path / "state"
    root.mkdir(parents=True)
    (root / "not_a_slot.json").write_text("[1, 2, 3]\n", encoding="utf-8")
    assert read_state_slot("not.a.slot", root) is None


def test_cli_parse_reports_errors_instead_of_tracebacks(tmp_path: Path, capsys):
    assert main(["parse", str(tmp_path / "nope.md")]) == 2  # used to raise FileNotFoundError
    assert "cannot read" in capsys.readouterr().err

    plain = tmp_path / "2026-09-05_1200_grok_plain.md"
    plain.write_text("---\nfrom: grok\ndate: 2026-09-05T12:00:00+00:00\n---\n\nhola\n", encoding="utf-8")
    assert main(["parse", str(plain)]) == 1
    assert "not an EICP message" in capsys.readouterr().err


def test_cli_emit_rejects_bad_type_with_exit_2(capsys):
    assert main(["emit", "--from", "grok", "--type", "nope", "--body", "x"]) == 2
    assert "type must be one of" in capsys.readouterr().err


def test_embedded_message_passes_the_bridge_validator(tmp_path: Path):
    """An EICP message is also an AI Bridge message: it must pass both halves."""
    msg = build_message(sender="arena", msg_type="comment", body="integración",
                        thread="eicp-spec", date="2026-09-05T12:00:00+00:00")
    p = tmp_path / "2026-09-05_1200_arena_integracion.md"
    p.write_text(embed_markdown(msg), encoding="utf-8")
    r = validate_file(p, now=NOW)
    assert r.is_valid, [e.message for e in r.errors]
    assert not r.warnings, [w.message for w in r.warnings]
