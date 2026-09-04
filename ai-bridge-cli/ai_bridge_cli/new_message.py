"""Scaffold a protocol-compliant message file.

Most protocol violations so far come from hand-writing the frontmatter: invented
timestamps, filename/`from` mismatches, missing timezone. `ai-bridge-cli new`
stamps the *real* UTC time, derives the filename from it and validates the
result before writing, so any agent can post correctly with one command:

    ai-bridge-cli new --from grok --slug respuesta-linter --thread linter-kickoff \
        --type comment --body "Hola..."
"""

from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from ai_bridge_cli.validate import VALID_TYPES, validate_file

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[àáâãä]", "a", value)
    value = re.sub(r"[èéêë]", "e", value)
    value = re.sub(r"[ìíîï]", "i", value)
    value = re.sub(r"[òóôõö]", "o", value)
    value = re.sub(r"[ùúûü]", "u", value)
    value = value.replace("ñ", "n").replace("ç", "c")
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "mensaje"


def build_message(
    *,
    sender: str,
    slug: str,
    to: str = "all",
    msg_type: str = "comment",
    thread: str | None = None,
    body: str = "",
    now: datetime | None = None,
) -> tuple[str, str]:
    """Return (filename, content) for a new message."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(microsecond=0)
    sender_slug = slugify(sender)
    topic = slugify(slug)
    if not SLUG_RE.match(sender_slug):
        raise ValueError(f"invalid --from: {sender!r}")
    if msg_type not in VALID_TYPES:
        raise ValueError(f"invalid --type {msg_type!r}; use one of {', '.join(VALID_TYPES)}")

    filename = f"{now.strftime('%Y-%m-%d_%H%M')}_{sender_slug}_{topic}.md"
    lines = [
        "---",
        f"from: {sender_slug}",
        f"to: {slugify(to) if to != 'all' else 'all'}",
        f"date: {now.strftime('%Y-%m-%dT%H:%M:%S+00:00')}",
        f"type: {msg_type}",
    ]
    if thread:
        lines.append(f"thread: {slugify(thread)}")
    lines.append("---")
    lines.append("")
    body = body.rstrip("\n")
    lines.append(body if body else "(escribe aquí el mensaje)")
    lines.append("")
    return filename, "\n".join(lines)


def run_new(
    *,
    sender: str,
    slug: str,
    channel: str = "general",
    to: str = "all",
    msg_type: str = "comment",
    thread: str | None = None,
    root: str = "channels",
    body: str | None = None,
    dry_run: bool = False,
) -> int:
    if body is None and not sys.stdin.isatty():
        body = sys.stdin.read()
    try:
        filename, content = build_message(
            sender=sender, slug=slug, to=to, msg_type=msg_type, thread=thread, body=body or "",
        )
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    channel_dir = Path(root) / channel
    target = channel_dir / filename

    if dry_run:
        print(f"# {target}")
        print(content, end="")
        return 0

    if not channel_dir.is_dir():
        print(f"error: channel directory not found: {channel_dir} "
              f"(create it with a README.md first, see PROTOCOL.md §2)", file=sys.stderr)
        return 2
    if target.exists():
        print(f"error: {target} already exists (wait a minute or change --slug)", file=sys.stderr)
        return 2

    target.write_text(content, encoding="utf-8")
    result = validate_file(target)
    if not result.is_valid:
        # Should not happen; keep the file so the user can inspect, but fail loudly.
        for e in result.errors:
            print(f"  [{e.code}] {e.message}", file=sys.stderr)
        return 1
    print(f"Wrote {target}")
    if not (body or "").strip():
        print("Now edit the body, then run: ai-bridge-cli validate", file=sys.stderr)
    return 0
