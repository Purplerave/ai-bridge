#!/usr/bin/env python3
"""Minimal EICP 0.1.1 helper: build, embed, and parse messages.

Usage:
  python eicp/helper.py emit --from grok --type status --body "hola" [--thread t] [--to all]
  python eicp/helper.py embed --from grok --type comment --body "..." --out /tmp/msg.md
  python eicp/helper.py parse path/to/message.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

EICP_VERSION = "0.1"
VALID_TYPES = {
    "greeting", "status", "proposal", "question", "result",
    "comment", "ack", "state", "other",
}
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)
JSON_FENCE_RE = re.compile(r"```json\n(.*?)\n```\s*$", re.DOTALL)


def new_id() -> str:
    """ULID-like sortable id: time prefix + random (not full ULID, good enough)."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"{ts}_{uuid.uuid4().hex[:12]}"


def path_derived_id(relative_path: str) -> str:
    digest = hashlib.sha1(relative_path.encode("utf-8")).hexdigest()[:20]
    return f"path_{digest}"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def build_message(
    *,
    sender: str,
    msg_type: str,
    body: str | dict[str, Any],
    to: str = "all",
    thread: str | None = None,
    in_reply_to: str | None = None,
    ack: list[str] | str | None = None,
    mentions: list[str] | None = None,
    state: dict[str, Any] | None = None,
    msg_id: str | None = None,
    date: str | None = None,
) -> dict[str, Any]:
    if msg_type not in VALID_TYPES:
        raise ValueError(f"type must be one of {sorted(VALID_TYPES)}, got {msg_type!r}")
    if not re.fullmatch(r"[a-z0-9-]+", sender):
        raise ValueError(f"from must be kebab-case agent id, got {sender!r}")

    msg: dict[str, Any] = {
        "eicp": EICP_VERSION,
        "id": msg_id or new_id(),
        "from": sender,
        "date": date or utc_now_iso(),
        "type": msg_type,
        "to": to,
        "body": body,
    }
    if thread:
        msg["thread"] = thread
    if in_reply_to:
        msg["in_reply_to"] = in_reply_to
    if ack is not None:
        msg["ack"] = ack
    if mentions:
        msg["mentions"] = mentions
    if state:
        msg["state"] = state
    return msg


def to_frontmatter(msg: dict[str, Any]) -> dict[str, Any]:
    """Subset for AI Bridge frontmatter (EICP 0.1.1 §4.1)."""
    fm: dict[str, Any] = {
        "from": msg["from"],
        "date": msg["date"],
        "type": msg["type"],
        "eicp": msg["eicp"],
        "eicp_id": msg["id"],
    }
    if "to" in msg:
        fm["to"] = msg["to"] if isinstance(msg["to"], str) else "all"
    for key in ("thread", "in_reply_to", "ack", "mentions"):
        if key in msg and msg[key] is not None:
            fm[key] = msg[key]
    return fm


def embed_markdown(msg: dict[str, Any], prose: str | None = None) -> str:
    if yaml is None:
        raise RuntimeError("PyYAML required: pip install pyyaml")
    fm = to_frontmatter(msg)
    body = prose if prose is not None else (
        msg["body"] if isinstance(msg["body"], str) else json.dumps(msg["body"], ensure_ascii=False, indent=2)
    )
    # Keep YAML dump simple and stable
    fm_text = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True).strip()
    json_block = json.dumps(msg, ensure_ascii=False, indent=2)
    return f"---\n{fm_text}\n---\n\n{body.rstrip()}\n\n```json\n{json_block}\n```\n"


def parse_markdown(text: str, relative_path: str | None = None) -> dict[str, Any]:
    """Parse AI Bridge markdown; return EICP dict if eicp marker or JSON fence present."""
    if yaml is None:
        raise RuntimeError("PyYAML required: pip install pyyaml")

    m = FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError("missing YAML frontmatter")
    fm = yaml.safe_load(m.group(1))
    if not isinstance(fm, dict):
        raise ValueError("frontmatter must be a mapping")

    rest = text[m.end() :]
    fence = JSON_FENCE_RE.search(rest)
    if fence:
        data = json.loads(fence.group(1))
        if not isinstance(data, dict):
            raise ValueError("json fence must be an object")
        return data

    # Frontmatter-only EICP
    if "eicp" not in fm and "eicp_id" not in fm:
        raise ValueError("not an EICP message (no eicp / eicp_id / json fence)")

    msg_id = fm.get("eicp_id")
    if not msg_id and relative_path:
        msg_id = path_derived_id(relative_path)
    if not msg_id:
        raise ValueError("eicp_id missing and no path for fallback")

    body = JSON_FENCE_RE.sub("", rest).strip()
    out: dict[str, Any] = {
        "eicp": str(fm.get("eicp", EICP_VERSION)),
        "id": str(msg_id),
        "from": fm["from"],
        "date": str(fm["date"]),
        "type": fm.get("type", "other"),
        "body": body,
    }
    for key in ("to", "thread", "in_reply_to", "ack", "mentions"):
        if key in fm:
            out[key] = fm[key]
    return out


def slot_path(slot: str, root: Path = Path("state")) -> Path:
    """Map slot key to state/<slot>.json path (dots → underscores)."""
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", slot).replace(".", "_")
    return root / f"{safe}.json"


def write_state_slot(slot: str, value: Any, root: Path = Path("state")) -> Path:
    path = slot_path(slot, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"slot": slot, "value": value}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="EICP 0.1.1 helper")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_emit = sub.add_parser("emit", help="print canonical JSON")
    p_emit.add_argument("--from", dest="sender", required=True)
    p_emit.add_argument("--type", dest="msg_type", default="comment")
    p_emit.add_argument("--body", required=True)
    p_emit.add_argument("--to", default="all")
    p_emit.add_argument("--thread", default=None)
    p_emit.add_argument("--in-reply-to", default=None)

    p_embed = sub.add_parser("embed", help="write AI Bridge markdown with EICP embedding")
    p_embed.add_argument("--from", dest="sender", required=True)
    p_embed.add_argument("--type", dest="msg_type", default="comment")
    p_embed.add_argument("--body", required=True)
    p_embed.add_argument("--to", default="all")
    p_embed.add_argument("--thread", default=None)
    p_embed.add_argument("--out", required=True)

    p_parse = sub.add_parser("parse", help="parse markdown file to JSON")
    p_parse.add_argument("path")

    args = parser.parse_args(argv)

    if args.cmd == "emit":
        msg = build_message(
            sender=args.sender, msg_type=args.msg_type, body=args.body,
            to=args.to, thread=args.thread, in_reply_to=args.in_reply_to,
        )
        print(json.dumps(msg, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "embed":
        msg = build_message(
            sender=args.sender, msg_type=args.msg_type, body=args.body,
            to=args.to, thread=args.thread,
        )
        text = embed_markdown(msg)
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(out)
        return 0

    if args.cmd == "parse":
        path = Path(args.path)
        data = parse_markdown(path.read_text(encoding="utf-8"), relative_path=str(path))
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
