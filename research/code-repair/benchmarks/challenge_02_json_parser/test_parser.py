import sys
from pathlib import Path

CHALLENGE_DIR = Path(__file__).resolve().parent
if str(CHALLENGE_DIR) not in sys.path:
    sys.path.insert(0, str(CHALLENGE_DIR))

from json_parser import parse_safe_json, extract_key  # noqa: E402


def test_parse_safe_json():
    assert parse_safe_json('{"key": "value"}') == {"key": "value"}
    assert parse_safe_json('invalid json', default=[]) == []
    assert parse_safe_json(None, default="fallback") == "fallback"


def test_extract_key():
    json_data = '{"name": "Jules", "role": "AI"}'
    assert extract_key(json_data, "name") == "Jules"
    assert extract_key(json_data, "missing", "N/A") == "N/A"
    assert extract_key("invalid", "name", "N/A") == "N/A"
