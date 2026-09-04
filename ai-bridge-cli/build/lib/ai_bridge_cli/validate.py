import re
from datetime import datetime, timezone
from pathlib import Path

REQUIRED_FRONTMATTER_FIELDS = {"from", "date"}
VALID_TYPES = {"greeting", "question", "proposal", "result", "status", "comment", "other"}
FILENAME_PATTERN = re.compile(
    r"^(\d{4}-\d{2}-\d{2}(_\d{4})?|(\d{3})_)[a-z0-9_-]+\.md$"
)


def _parse_frontmatter(text: str):
    if not text.startswith("---"):
        return None, text
    end = text.find("---", 3)
    if end == -1:
        return None, text
    fm = text[3:end].strip()
    rest = text[end + 3 :].strip()
    return fm, rest


def _parse_yaml_safe(raw: str):
    import yaml

    try:
        data = yaml.safe_load(raw)
        if not isinstance(data, dict):
            return None
        return data
    except yaml.YAMLError:
        return None


def _validate_date(value) -> list[str]:
    errors = []
    if isinstance(value, datetime):
        value = value.isoformat()
    if not isinstance(value, str):
        errors.append("`date` must be a string")
        return errors
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            errors.append("`date` must include timezone offset (ISO 8601)")
    except ValueError:
        errors.append("`date` is not valid ISO 8601")
    return errors


def _validate_filename(path: Path) -> list[str]:
    errors = []
    name = path.name
    if not FILENAME_PATTERN.match(name):
        errors.append(
            "Filename must match YYYY-MM-DD[_HHMM]_from_slug.md or NNN_from_slug.md"
        )
    return errors


def validate_file(path: Path) -> tuple[bool, list[str]]:
    errors: list[str] = []

    raw = path.read_bytes()
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        errors.append("File is not valid UTF-8")

    text = raw.decode("utf-8", errors="replace")
    frontmatter, body = _parse_frontmatter(text)
    if frontmatter is None:
        errors.append("Missing YAML frontmatter (must start with ---)")
        return False, errors

    data = _parse_yaml_safe(frontmatter)
    if data is None:
        errors.append("Frontmatter YAML is invalid")
        return False, errors

    for field in REQUIRED_FRONTMATTER_FIELDS:
        if field not in data:
            errors.append(f"Missing required frontmatter field: `{field}`")

    if "date" in data:
        errors.extend(_validate_date(data["date"]))

    if "type" in data and data["type"] not in VALID_TYPES:
        errors.append(f"Unknown `type`: {data['type']}")

    errors.extend(_validate_filename(path))

    if not body.strip():
        errors.append("Message body is empty")

    return len(errors) == 0, errors


def validate_path(root: str | Path) -> tuple[int, int, dict[str, list[str]]]:
    root = Path(root)
    results: dict[str, list[str]] = {}
    total = 0
    ok = 0
    for path in sorted(root.rglob("*.md")):
        if path.name == "README.md":
            continue
        total += 1
        valid, errs = validate_file(path)
        if valid:
            ok += 1
        else:
            results[str(path)] = errs
    return ok, total, results


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(prog="ai-bridge-cli")
    parser.add_argument("path", nargs="?", default="channels", help="Root path to validate")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    ok, total, results = validate_path(args.path)
    if args.json:
        import json

        print(json.dumps({"valid": ok, "total": total, "errors": results}, ensure_ascii=False, indent=2))
    else:
        if results:
            print(f"Validation failed: {total - ok}/{total} files with errors")
            for path, errs in results.items():
                print(f"- {path}")
                for e in errs:
                    print(f"  * {e}")
        else:
            print(f"Validation passed: {ok}/{total} files OK")


if __name__ == "__main__":
    main()
