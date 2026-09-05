"""Tests for eicp/helper.py — run: pytest eicp/test_helper.py -q"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from helper import (
    build_message,
    embed_markdown,
    parse_markdown,
    path_derived_id,
    slot_path,
    write_state_slot,
)


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
