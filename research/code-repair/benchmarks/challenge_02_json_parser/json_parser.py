import json


def parse_safe_json(json_str: str, default=None):
    if not json_str or not isinstance(json_str, str):
        return default
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return default


def extract_key(json_str: str, key: str, default=None):
    data = parse_safe_json(json_str, default={})
    if isinstance(data, dict):
        return data.get(key, default)
    return default
