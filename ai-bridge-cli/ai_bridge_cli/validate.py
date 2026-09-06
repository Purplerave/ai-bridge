"""AI Bridge Protocol Message Validator.

Errors (fail validation):
- ENCODING       file is not UTF-8, or has a BOM
- FILENAME       name != YYYY-MM-DD[_HHMM]_from_slug.md | NNN_from_slug.md
- FRONTMATTER    missing / malformed / not a YAML mapping
- FIELD_MISSING  required field absent or empty (`from`, `date`)
- FIELD_FORMAT   `from` / `to` / `thread` are not plain strings
- DATE_FORMAT    `date` is not strict ISO 8601 with timezone, or not a real datetime
- TYPE_INVALID   `type` not in VALID_TYPES

Warnings (reported, never fail unless --strict):
- MOJIBAKE       U+FFFD or Latin-1→UTF-8 double-encoding patterns (e.g. "Ã±", "â€")
- FILENAME_FROM  the `from` segment of the filename does not match `from`
- FILENAME_DATE  the date in the filename differs from the calendar date of `date`
- FILENAME_TIME  the HHMM in the filename differs from the wall-clock time of `date`
- DATE_FUTURE    `date` is ahead of the current time (invented timestamps)
- BODY_EMPTY     nothing but frontmatter: the message carries no content

Structural files (`README.md`, `INDEX.md`, `STATUS.md` — PROTOCOL.md §7) are
skipped wherever they appear: they are not messages. Code blocks and inline
code are excluded from MOJIBAKE, so a message can quote a broken sequence to
explain it without raising the warning.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

ERROR = "error"
WARNING = "warning"


@dataclass
class ValidationIssue:
    file: Path
    line: int | None
    code: str
    message: str
    severity: str = ERROR


# Backwards-compatible alias (older code/tests import ValidationError).
ValidationError = ValidationIssue


@dataclass
class ValidationResult:
    file: Path
    errors: list[ValidationIssue]
    frontmatter: dict | None = None
    warnings: list[ValidationIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    @property
    def issues(self) -> list[ValidationIssue]:
        return [*self.errors, *self.warnings]


class _StringSafeLoader(yaml.SafeLoader):
    """SafeLoader that keeps scalars as strings.

    PyYAML's implicit resolvers turn `date: 2026-09-04T13:40:00+00:00` into a
    datetime (and crash on offsets like +25:00), `thread: 001` into the int 1
    and `to: yes` into True. Frontmatter fields are identifiers and ISO strings,
    so we only keep the null resolver (empty values -> None) and validate the
    raw text ourselves.
    """


_StringSafeLoader.yaml_implicit_resolvers = {
    ch: [(tag, regexp) for tag, regexp in resolvers if tag == "tag:yaml.org,2002:null"]
    for ch, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}

FRONTMATTER_RE = re.compile(r"^---[ \t]*\n(.*?)\n---[ \t]*(?:\n|$)", re.DOTALL)
FILENAME_RE = re.compile(
    r"^(?:(?P<date>\d{4}-\d{2}-\d{2})(?:_(?P<time>\d{4}))?|(?P<seq>\d{3}))"
    r"_(?P<rest>[a-z0-9][a-z0-9_-]*)\.md$"
)
ISO8601_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})$"
)
# U+FFFD, or the classic UTF-8-read-as-Latin-1 sequences: "Ã±" "Ã©" "Â¿" "â€”"
MOJIBAKE_RE = re.compile("\ufffd|\u00c3[\u0080-\u00bf]|\u00c2[\u00a0-\u00bf]|\u00e2\u20ac")
# Fenced blocks (``` / ~~~) and inline code spans: legitimate places to *quote*
# a broken sequence (e.g. documenting this very rule), so they are masked out
# before the mojibake heuristic runs.
FENCED_CODE_RE = re.compile(r"^(?:```|~~~).*?$(?:.*?)^(?:```|~~~)[ \t]*$", re.DOTALL | re.MULTILINE)
# ``...`` first: it may legitimately contain a single backtick (`` `x` ``).
INLINE_CODE_RE = re.compile(r"``.+?``|`[^`\n]*`")

REQUIRED_FIELDS = ("from", "date")
STRING_FIELDS = ("from", "to", "thread")
VALID_TYPES = ("greeting", "question", "proposal", "result", "status", "comment", "ack", "state", "other")
FUTURE_TOLERANCE = timedelta(minutes=15)

# PROTOCOL.md §7: these files describe a directory or are regenerated in place.
# They are never messages, wherever they live, so both the validator and the
# indexer skip them by name.
STRUCTURAL_FILENAMES = frozenset({"readme.md", "index.md", "status.md"})


def is_structural(path: Path) -> bool:
    """True for `README.md` / `INDEX.md` / `STATUS.md` (PROTOCOL.md §7)."""
    return path.name.lower() in STRUCTURAL_FILENAMES


def _line_of(content: str, offset: int) -> int:
    """1-based line number containing the character at `offset`."""
    return content.count("\n", 0, offset) + 1


def _field_line(raw_fm: str, name: str) -> int | None:
    """1-based line number (in the file) of a top-level frontmatter key."""
    for i, line in enumerate(raw_fm.split("\n"), start=2):  # line 1 is the opening ---
        if re.match(rf"^{re.escape(name)}\s*:", line):
            return i
    return None


def _normalize_name(value: str) -> str:
    return re.sub(r"\s+", "-", value.strip().lower())


def _parse_date(raw: str) -> datetime | None:
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _mask(text: str, pattern: re.Pattern[str]) -> str:
    """Blank out `pattern` matches, keeping length and line numbers intact."""
    chars = list(text)
    for m in pattern.finditer(text):
        for i in range(m.start(), m.end()):
            if chars[i] != "\n":
                chars[i] = " "
    return "".join(chars)


def mask_code(content: str) -> str:
    """Replace code blocks and inline code with spaces (same offsets/lines)."""
    return _mask(_mask(content, FENCED_CODE_RE), INLINE_CODE_RE)


def validate_file(path: Path, *, now: datetime | None = None) -> ValidationResult:
    """Validate a single message file.

    `now` is only used for the DATE_FUTURE warning (injectable for tests).
    """
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    frontmatter: dict | None = None

    def err(line: int | None, code: str, message: str) -> None:
        errors.append(ValidationIssue(path, line, code, message, ERROR))

    def warn(line: int | None, code: str, message: str) -> None:
        warnings.append(ValidationIssue(path, line, code, message, WARNING))

    # 1. UTF-8
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        err(1, "ENCODING", f"Not valid UTF-8: {e}")
        return ValidationResult(path, errors, None, warnings)

    # 2. BOM
    if content.startswith("\ufeff"):
        err(1, "ENCODING", "UTF-8 BOM detected (not allowed)")
        content = content[1:]

    # 3. Mojibake heuristic (valid UTF-8, but visibly corrupted text).
    #    Code spans are masked: quoting a broken sequence to *explain* it is
    #    legitimate, so only prose is checked.
    prose = mask_code(content)
    m = MOJIBAKE_RE.search(prose)
    if m:
        line = _line_of(content, m.start())
        count = len(MOJIBAKE_RE.findall(prose))
        warn(line, "MOJIBAKE",
             f"{count} suspicious sequence(s) like {m.group(0)!r}: text looks encoding-corrupted "
             "(U+FFFD or Latin-1/UTF-8 double encoding)")

    # 4. Filename
    fn = FILENAME_RE.match(path.name)
    if not fn:
        err(None, "FILENAME",
            f"'{path.name}' != YYYY-MM-DD[_HHMM]_from_slug.md | NNN_from_slug.md "
            "(lowercase a-z, 0-9, '-' and '_')")

    # 5. Frontmatter
    fm_match = FRONTMATTER_RE.match(content)
    raw_fm = fm_match.group(1) if fm_match else None
    if raw_fm is None:
        if content.lstrip(" \t\r\n").startswith("---"):
            err(1, "FRONTMATTER", "Frontmatter must start on line 1 (found leading blank lines/whitespace)")
        else:
            err(1, "FRONTMATTER", "Missing or malformed frontmatter block (---\\n...\\n---)")
        return ValidationResult(path, errors, None, warnings)

    try:
        frontmatter = yaml.load(raw_fm, Loader=_StringSafeLoader)
    except (yaml.YAMLError, ValueError) as e:
        mark = getattr(e, "problem_mark", None)
        where = f" at line {mark.line + 2}" if mark is not None else ""
        err(1, "FRONTMATTER", f"YAML parse error{where}: {getattr(e, 'problem', e)}")
        return ValidationResult(path, errors, None, warnings)

    if not isinstance(frontmatter, dict):
        err(1, "FRONTMATTER", "Frontmatter must be a YAML mapping (key: value)")
        return ValidationResult(path, errors, None, warnings)

    # 6. Required fields (absent or empty)
    for name in REQUIRED_FIELDS:
        if name not in frontmatter:
            err(1, "FIELD_MISSING", f"'{name}' is required")
        elif frontmatter[name] is None or (isinstance(frontmatter[name], str) and not frontmatter[name].strip()):
            err(_field_line(raw_fm, name), "FIELD_MISSING", f"'{name}' is present but empty")

    # 7. String-only fields
    for name in STRING_FIELDS:
        value = frontmatter.get(name)
        if value is not None and not isinstance(value, str):
            err(_field_line(raw_fm, name), "FIELD_FORMAT",
                f"'{name}' must be a plain string, got {type(value).__name__}: {value!r}")

    # 8. date — strict ISO 8601 with explicit timezone, and a real datetime
    parsed_date: datetime | None = None
    raw_date = frontmatter.get("date")
    if isinstance(raw_date, str) and raw_date.strip():
        raw_date = raw_date.strip()
        date_line = _field_line(raw_fm, "date")
        if not ISO8601_RE.match(raw_date):
            err(date_line, "DATE_FORMAT",
                f"date must be ISO 8601 with timezone (YYYY-MM-DDTHH:MM:SS+HH:MM or ...Z), got: {raw_date}")
        else:
            parsed_date = _parse_date(raw_date)
            if parsed_date is None:
                err(date_line, "DATE_FORMAT", f"Invalid datetime (impossible month/day/hour/offset): {raw_date}")
            else:
                current = now or datetime.now(timezone.utc)
                ahead = parsed_date - current
                if ahead > FUTURE_TOLERANCE:
                    hours = ahead.total_seconds() / 3600
                    warn(date_line, "DATE_FUTURE",
                         f"date is {hours:.1f}h in the future; use the real time of writing "
                         "(e.g. `date -u +%Y-%m-%dT%H:%M:%S+00:00`)")
    elif raw_date is not None and not isinstance(raw_date, str):
        err(_field_line(raw_fm, "date"), "DATE_FORMAT",
            f"date must be a string, got {type(raw_date).__name__}: {raw_date!r}")

    # 9. type
    if "type" in frontmatter and frontmatter["type"] not in VALID_TYPES:
        err(_field_line(raw_fm, "type"), "TYPE_INVALID",
            f"type must be one of {', '.join(VALID_TYPES)}; got: {frontmatter['type']!r}")

    # 10. Filename <-> frontmatter consistency (warnings)
    if fn:
        from_value = frontmatter.get("from")
        if isinstance(from_value, str) and from_value.strip():
            expected = _normalize_name(from_value)
            rest = fn.group("rest")
            if not (rest == expected or rest.startswith(expected + "_")):
                actual = rest.split("_", 1)[0]
                prefix = fn.group("date") or fn.group("seq")
                if fn.group("time"):
                    prefix += "_" + fn.group("time")
                warn(None, "FILENAME_FROM",
                     f"filename segment '{actual}' != from '{expected}' "
                     f"(expected {prefix}_{expected}_<slug>.md)")
        if parsed_date is not None:
            if fn.group("date") and fn.group("date") != parsed_date.strftime("%Y-%m-%d"):
                warn(None, "FILENAME_DATE",
                     f"filename date {fn.group('date')} != date {parsed_date.strftime('%Y-%m-%d')}")
            if fn.group("time") and fn.group("time") != parsed_date.strftime("%H%M"):
                warn(None, "FILENAME_TIME",
                     f"filename time {fn.group('time')} != date wall-clock {parsed_date.strftime('%H%M')} "
                     f"(same timezone as `date`, {parsed_date.strftime('%z')})")

    # 11. Body carries content (PROTOCOL.md §3). Warning, not error: a message
    #     that is only frontmatter is useless but harmless, and `new` writes a
    #     placeholder body on purpose.
    if fm_match is not None and not content[fm_match.end():].strip():
        warn(_line_of(content, fm_match.end()), "BODY_EMPTY",
             "no content after the frontmatter; write the message body (PROTOCOL.md §3)")

    return ValidationResult(path, errors, frontmatter, warnings)


def validate_dir(path: Path, pattern: str = "**/*.md", *, now: datetime | None = None) -> list[ValidationResult]:
    files = sorted(
        [f for f in path.glob(pattern) if f.is_file() and not is_structural(f)],
        key=lambda f: f.as_posix(),
    )
    return [validate_file(f, now=now) for f in files]


def run_validate(path: str = "channels", as_json: bool = False, strict: bool = False) -> int:
    """Validate a directory. Exit codes: 0 ok, 1 errors (or warnings with --strict), 2 nothing to validate."""
    root = Path(path)
    if not root.exists():
        print(f"Not found: {root}", file=sys.stderr)
        return 2

    results = validate_dir(root) if root.is_dir() else [validate_file(root)]
    total_errors = sum(len(r.errors) for r in results)
    total_warnings = sum(len(r.warnings) for r in results)

    if as_json:
        import json
        print(json.dumps({
            "files": len(results),
            "errors": total_errors,
            "warnings": total_warnings,
            "strict": strict,
            "results": [
                {
                    "file": str(r.file),
                    "valid": r.is_valid,
                    "errors": [{"code": e.code, "line": e.line, "message": e.message} for e in r.errors],
                    "warnings": [{"code": w.code, "line": w.line, "message": w.message} for w in r.warnings],
                }
                for r in results
            ],
        }, indent=2, ensure_ascii=False))
    else:
        for r in results:
            status = "FAIL" if not r.is_valid else ("WARN" if r.warnings else "OK  ")
            print(f"{status} {r.file}")
            for issue in r.issues:
                where = f"L{issue.line}: " if issue.line is not None else ""
                label = "" if issue.severity == ERROR else "warning: "
                print(f"  [{issue.code}] {where}{label}{issue.message}")
        print(f"\nFiles: {len(results)} | Errors: {total_errors} | Warnings: {total_warnings}")
        if not results:
            print(f"No message files found under {root} (README.md is ignored)", file=sys.stderr)

    if not results:
        return 2
    if total_errors or (strict and total_warnings):
        return 1
    return 0


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Validate AI Bridge messages")
    parser.add_argument("path", nargs="?", default="channels")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true", help="treat warnings as errors")
    args = parser.parse_args()
    return run_validate(args.path, args.json, args.strict)


if __name__ == "__main__":
    sys.exit(main())
