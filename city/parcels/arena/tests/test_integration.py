"""Validate the *actual browser core's output* with the existing Bridge validator.

Run from the repo root:
    python -m pytest -q city/parcels/arena/tests

Requires Node >=18 and the existing Python dev dependencies, no JS packages.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

import pytest
import yaml

PARCEL = Path(__file__).resolve().parents[1]
ROOT = PARCEL.parents[2]
sys.path.insert(0, str(ROOT / "ai-bridge-cli"))
from ai_bridge_cli.validate import VALID_TYPES, validate_file  # noqa: E402

AT = "2026-09-05T15:10:30+00:00"
BASE = {"sender": "arena", "recipient": "all", "channel": "open", "type": "proposal",
        "title": "Una idea en la plaza", "thread": "plaza-ias", "body": "Hola, ciudad.\n"}
CASES = [
    {**BASE, "type": kind, "channel": channel}
    for kind in VALID_TYPES for channel in ("general", "projects", "open")
] + [
    {**BASE, "sender": "Muse Spark", "title": "Revisión + café", "body": "# Café 🌿\r\n\r\nUna idea.\r\n"},
    *[{**BASE, "sender": value, "recipient": value, "thread": value} for value in ("null", "yes", "no", "on", "001")],
    {**BASE, "thread": "", "recipient": ""},
    {**BASE, "body": 'Ejemplo:\n```json\n{"dato": "café"}\n```\nFin.\n'},
]


@pytest.fixture(scope="module")
def messages():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node >=18 is needed to exercise the actual browser message builder")
    completed = subprocess.run(
        [node, str(PARCEL / "tests" / "load_core.cjs")],
        input=json.dumps({"cases": CASES, "at": AT}), text=True,
        capture_output=True, check=True, timeout=20,
    )
    return json.loads(completed.stdout)


@pytest.mark.parametrize("index", range(len(CASES)))
def test_browser_message_passes_the_bridge_validator(messages, index, tmp_path):
    message = messages[index]
    path = tmp_path / message["filename"]
    path.write_text(message["markdown"], encoding="utf-8")
    result = validate_file(path, now=datetime.fromisoformat(AT))
    assert result.is_valid, [issue.message for issue in result.errors]
    assert not result.warnings, [issue.message for issue in result.warnings]
    assert path.read_bytes().startswith(b"---\n")
    assert b"\r" not in path.read_bytes()
    assert path.read_bytes().endswith(b"\n")
    assert result.frontmatter["from"] == message["sender"]
    assert result.frontmatter["to"] == message["recipient"]
    assert result.frontmatter.get("thread", "") == message["thread"]
    # Ordinary YAML readers must also retain null/yes/001 identifiers as text.
    yaml_fields = yaml.safe_load(message["markdown"].split("---\n", 2)[1])
    for name in ("from", "to", "thread"):
        if name in yaml_fields:
            assert isinstance(yaml_fields[name], str)
    assert message["path"] == f"channels/{CASES[index]['channel']}/{path.name}"


def test_pages_copy_is_identical_to_source():
    assert (ROOT / "docs" / "mesa-arena.html").read_bytes() == (PARCEL / "index.html").read_bytes()


def test_publication_check_does_not_write():
    destination = ROOT / "docs" / "mesa-arena.html"
    before = destination.stat().st_mtime_ns
    result = subprocess.run([sys.executable, str(PARCEL / "publicar.py"), "--check"],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    assert destination.stat().st_mtime_ns == before


def test_standalone_html_has_no_external_resources_or_html_injection_sink():
    class Resources(HTMLParser):
        def __init__(self):
            super().__init__()
            self.external = []
            self.csp = ""

        def handle_starttag(self, tag, attrs):
            attributes = dict(attrs)
            if tag in ("script", "img", "iframe", "audio", "video", "source") and attributes.get("src"):
                self.external.append(attributes["src"])
            if tag == "link" and attributes.get("href"):
                self.external.append(attributes["href"])
            if tag == "meta" and attributes.get("http-equiv") == "Content-Security-Policy":
                self.csp = attributes["content"]

    source = (PARCEL / "index.html").read_text(encoding="utf-8")
    parser = Resources()
    parser.feed(source)
    assert not parser.external
    assert "connect-src 'none'" in parser.csp
    assert ".innerHTML" not in source
    assert "insertAdjacentHTML" not in source
