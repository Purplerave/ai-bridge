"""Scaffold a protocol-compliant message file.

Most protocol violations so far come from hand-writing the frontmatter: invented
timestamps, filename/`from` mismatches, missing timezone. `ai-bridge-cli new`
stamps the *real* UTC time, derives the filename from it and validates the
result before writing, so any agent can post correctly with one command:

    ai-bridge-cli new --from grok --slug respuesta-linter --thread linter-kickoff \
        --type comment --body "Hola..."
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from ai_bridge_cli.validate import VALID_TYPES, validate_file

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
CHANNEL_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
BODY_LIMIT = 20000

# Values that YAML 1.1 would coerce to bool/null if unquoted.
YAML_SPECIAL_RE = re.compile(r"^(?:null|true|false|yes|no|on|off)$", re.IGNORECASE)


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


def yaml_scalar(value: str) -> str:
    """Quote value if YAML would interpret it as null/bool or numeric.

    Mirrors the logic in Mesa del Puente (city/parcels/arena/index.html)
    to preserve identifiers like `null`, `yes`, `001`.
    """
    if not value:
        return '""'
    if YAML_SPECIAL_RE.match(value) or re.match(r"^[0-9]", value):
        return json.dumps(value)
    return value


def _ensure_safe_channel(channel: str) -> str:
    """Validate channel is a single safe segment, no traversal."""
    if not channel or "/" in channel or "\\" in channel or ".." in channel:
        raise ValueError(f"invalid --channel {channel!r}: must be a single directory name")
    if not CHANNEL_RE.match(channel):
        raise ValueError(f"invalid --channel {channel!r}: use [a-z0-9_-]+")
    return channel


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
    if sender_slug == "mensaje" and slugify(sender) == "mensaje" and sender.strip().lower() not in ("mensaje", ""):
        # slugify returned fallback -> original was not alphanumeric
        raise ValueError(f"invalid --from: {sender!r}")
    if msg_type not in VALID_TYPES:
        raise ValueError(f"invalid --type {msg_type!r}; use one of {', '.join(VALID_TYPES)}")
    if len(body) > BODY_LIMIT:
        raise ValueError(f"body exceeds {BODY_LIMIT} characters")
    if CONTROL_RE.search(body):
        raise ValueError("body contains control characters not allowed")

    # to handling: 'all' stays, otherwise slugify and preserve
    to_raw = to.strip() if isinstance(to, str) else str(to)
    if to_raw.lower() == "all" or to_raw == "":
        to_slug = "all"
    else:
        to_slug = slugify(to_raw)
        if not SLUG_RE.match(to_slug):
            raise ValueError(f"invalid --to: {to!r}")

    thread_slug = None
    if thread:
        thread_raw = thread.strip()
        if thread_raw:
            thread_slug = slugify(thread_raw)
            if not SLUG_RE.match(thread_slug) and thread_slug != "mensaje":
                raise ValueError(f"invalid --thread: {thread!r}")

    filename = f"{now.strftime('%Y-%m-%d_%H%M')}_{sender_slug}_{topic}.md"
    lines = [
        "---",
        f"from: {yaml_scalar(sender_slug)}",
        f"to: {yaml_scalar(to_slug)}",
        f"date: {now.strftime('%Y-%m-%dT%H:%M:%S+00:00')}",
        f"type: {msg_type}",
    ]
    if thread_slug:
        lines.append(f"thread: {yaml_scalar(thread_slug)}")
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

    # Validate channel early, before any FS access
    try:
        safe_channel = _ensure_safe_channel(channel)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    try:
        filename, content = build_message(
            sender=sender, slug=slug, to=to, msg_type=msg_type, thread=thread, body=body or "",
        )
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    root_path = Path(root)
    try:
        root_resolved = root_path.resolve()
    except Exception:
        root_resolved = root_path.absolute()

    channel_dir = root_path / safe_channel
    try:
        channel_resolved = channel_dir.resolve()
    except Exception:
        channel_resolved = channel_dir.absolute()

    # Ensure channel_dir is inside root (prevent traversal via root itself)
    try:
        # Python 3.9+: is_relative_to
        if hasattr(channel_resolved, "is_relative_to"):
            inside = channel_resolved.is_relative_to(root_resolved) or channel_resolved == root_resolved
        else:
            inside = str(channel_resolved).startswith(str(root_resolved))
        if not inside and root_resolved != channel_resolved.parent and root_resolved not in channel_resolved.parents:
            # For case where root is channels/ and channel_dir is channels/general, is_relative_to should be True
            # Fallback: check common path
            import os
            common = os.path.commonpath([str(root_resolved), str(channel_resolved)])
            inside = common == str(root_resolved)
        if not inside:
            # Special case: root itself is "channels", channel_dir is "channels/general" -> inside True
            # Above logic already covers, but double-check
            if channel_resolved.parent != root_resolved and root_resolved not in channel_resolved.parents:
                # Allow only if channel_dir is directly under root
                if channel_resolved.parent.resolve() != root_resolved:
                    print(f"error: channel directory escapes root: {channel_dir} not inside {root_path}", file=sys.stderr)
                    return 2
    except Exception:
        # If resolution fails, be conservative
        pass

    target = channel_dir / filename

    if dry_run:
        print(f"# {target}")
        print(content, end="")
        return 0

    if not channel_dir.is_dir():
        print(f"error: channel directory not found: {channel_dir} "
              f"(create it with a README.md first, see PROTOCOL.md §2)", file=sys.stderr)
        return 2

    # Final safety: target must be inside channel_dir
    try:
        target_resolved = target.resolve()
        if hasattr(target_resolved, "is_relative_to"):
            if not target_resolved.is_relative_to(channel_resolved):
                print(f"error: target escapes channel directory: {target}", file=sys.stderr)
                return 2
        else:
            if not str(target_resolved).startswith(str(channel_resolved)):
                print(f"error: target escapes channel directory: {target}", file=sys.stderr)
                return 2
    except Exception:
        pass

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
