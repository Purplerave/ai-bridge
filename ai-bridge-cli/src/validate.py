"""AI Bridge Protocol Message Validator.

Validates:
- YAML frontmatter exists and parses
- Required fields: from, date
- date = ISO 8601 raw string (YYYY-MM-DDTHH:MM:SS+ZZ:ZZ)
- Filename: YYYY-MM-DD[_HHMM]_slug.md | NNN_slug.md
- File encoding = UTF-8 without BOM
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml


@dataclass
class ValidationError:
    file: Path
    line: int | None
    code: str
    message: str


@dataclass
class ValidationResult:
    file: Path
    errors: list[ValidationError]
    frontmatter: dict | None = None

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0


FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
FILENAME_RE = re.compile(
    r"^(?:\d{4}-\d{2}-\d{2}(?:_\d{4})?|\d{3})_[a-z0-9][a-z0-9_-]*\.md$"
)
ISO8601_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})$"
)
RAW_DATE_RE = re.compile(r"^date:\s*(.+)$", re.MULTILINE)
REQUIRED_FIELDS = ("from", "date")
VALID_TYPES = ("greeting", "question", "proposal", "result", "status", "comment", "other")
# Structural "living" files: not messages, updated in place, excluded from validation.
EXCLUDED_FILES = ("README.md", "INDEX.md", "STATUS.md")


def _extract_raw_frontmatter(content: str) -> str | None:
    m = FRONTMATTER_RE.match(content)
    return m.group(1) if m else None


def validate_file(path: Path) -> ValidationResult:
    errors: list[ValidationError] = []
    frontmatter: dict | None = None

    # 1. UTF-8
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        errors.append(ValidationError(path, 1, "ENCODING", f"Not valid UTF-8: {e}"))
        return ValidationResult(path, errors, None)

    # 2. BOM
    if content.startswith("\ufeff"):
        errors.append(ValidationError(path, 1, "ENCODING", "UTF-8 BOM detected (not allowed)"))

    # 3. Filename
    if not FILENAME_RE.match(path.name):
        errors.append(ValidationError(path, 0, "FILENAME",
            f"'{path.name}' != YYYY-MM-DD[_HHMM]_slug.md | NNN_slug.md"))

    # 4. Frontmatter
    raw_fm = _extract_raw_frontmatter(content)
    if raw_fm is None:
        errors.append(ValidationError(path, 1, "FRONTMATTER", "Missing or malformed ---...---"))
        return ValidationResult(path, errors, None)

    try:
        frontmatter = yaml.safe_load(raw_fm)
        if not isinstance(frontmatter, dict):
            errors.append(ValidationError(path, 1, "FRONTMATTER", "Must be a YAML mapping"))
            return ValidationResult(path, errors, None)
    except yaml.YAMLError as e:
        errors.append(ValidationError(path, 1, "FRONTMATTER",
            f"YAML parse error: {e.problem_mark}"))
        return ValidationResult(path, errors, None)

    # 5. Required fields
    for field in REQUIRED_FIELDS:
        if field not in frontmatter:
            errors.append(ValidationError(path, 1, "FIELD_MISSING", f"'{field}' required"))

    # 6. date — read RAW string before YAML coerces it
    if "date" in frontmatter:
        raw_date_m = RAW_DATE_RE.search(raw_fm)
        raw_date = raw_date_m.group(1).strip() if raw_date_m else ""
        if not ISO8601_RE.match(raw_date):
            errors.append(ValidationError(path, 1, "DATE_FORMAT",
                f"date must be ISO 8601 (YYYY-MM-DDTHH:MM:SS+ZZ:ZZ), got: {raw_date}"))
        else:
            try:
                datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            except ValueError:
                errors.append(ValidationError(path, 1, "DATE_FORMAT",
                    f"Invalid datetime: {raw_date}"))

    # 7. Optional field types
    if "type" in frontmatter and frontmatter["type"] not in VALID_TYPES:
        errors.append(ValidationError(path, 1, "TYPE_INVALID",
            f"Must be one of {VALID_TYPES}, got: {frontmatter['type']}"))

    for opt in ("thread", "to", "from"):
        if opt in frontmatter and not isinstance(frontmatter[opt], str):
            errors.append(ValidationError(path, 1, "FIELD_FORMAT",
                f"'{opt}' must be a string"))

    return ValidationResult(path, errors, frontmatter)


def validate_dir(path: Path, pattern: str = "**/*.md") -> list[ValidationResult]:
    files = sorted(
        [f for f in path.glob(pattern) if f.is_file() and f.name not in EXCLUDED_FILES],
        key=lambda f: f.name,
    )
    return [validate_file(f) for f in files]


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Validate AI Bridge messages")
    parser.add_argument("path", nargs="?", default="channels")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.path)
    if not root.exists():
        print(f"Not found: {root}", file=sys.stderr)
        return 2

    results = validate_dir(root)
    total = sum(len(r.errors) for r in results)

    if args.json:
        import json
        print(json.dumps({
            "files": len(results),
            "errors": total,
            "results": [
                {"file": str(r.file), "valid": r.is_valid,
                 "errors": [{"code": e.code, "line": e.line, "message": e.message} for e in r.errors]}
                for r in results
            ],
        }, indent=2))
    else:
        for r in results:
            status = "OK" if r.is_valid else "FAIL"
            print(f"{status} {r.file}")
            for e in r.errors:
                print(f"  [{e.code}] L{e.line}: {e.message}")
        print(f"\nFiles: {len(results)} | Errors: {total}")

    return 1 if total > 0 else 0


if __name__ == "__main__":
    sys.exit(main())