"""AI Bridge Channel Indexer.

Reads all message files from channels/, parses frontmatter,
and generates channels/INDEX.md with a structured index.

Usage:
    python -m src.indexer channels/
    python -m src.indexer channels/ --output channels/INDEX.md
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import yaml


FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
RAW_DATE_RE = re.compile(r"^date:\s*(.+)$", re.MULTILINE)
RAW_FROM_RE = re.compile(r"^from:\s*(.+)$", re.MULTILINE)
RAW_TO_RE = re.compile(r"^to:\s*(.+)$", re.MULTILINE)
RAW_TYPE_RE = re.compile(r"^type:\s*(.+)$", re.MULTILINE)
RAW_THREAD_RE = re.compile(r"^thread:\s*(.+)$", re.MULTILINE)


def parse_message(path: Path) -> dict | None:
    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        return None

    fm_match = FRONTMATTER_RE.match(content)
    if not fm_match:
        return None

    raw = fm_match.group(1)
    try:
        data = yaml.safe_load(raw)
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    # Extract first line of body as title/summary
    body = content[fm_match.end():].strip()
    lines = [l.strip() for l in body.split("\n") if l.strip() and not l.strip().startswith("#")]
    summary = lines[0][:120] if lines else ""

    # Read raw date for sorting
    date_raw = ""
    dm = RAW_DATE_RE.search(raw)
    if dm:
        date_raw = dm.group(1).strip()

    return {
        "file": path,
        "from": data.get("from", "?"),
        "to": data.get("to", ""),
        "date": date_raw,
        "type": data.get("type", ""),
        "thread": data.get("thread", ""),
        "summary": summary,
    }


def index_dir(channels_dir: Path) -> dict[str, list[dict]]:
    """Group messages by channel name."""
    channels: dict[str, list[dict]] = defaultdict(list)

    for md in sorted(channels_dir.rglob("*.md"), key=lambda p: p.name):
        if md.name == "README.md" or md.name == "INDEX.md":
            continue
        if not md.is_file():
            continue

        # Channel = immediate parent of the .md file
        channel = md.parent.name if md.parent != channels_dir else "root"
        msg = parse_message(md)
        if msg:
            channels[channel].append(msg)

    # Sort each channel by date
    for ch in channels:
        channels[ch].sort(key=lambda m: m["date"])

    return dict(channels)


def generate_index(channels: dict[str, list[dict]], repo_root: Path) -> str:
    lines = [
        "# AI Bridge — Índice de Canales",
        "",
        f"_Generado automáticamente. Mensajes totales: {sum(len(v) for v in channels.values())}_",
        "",
    ]

    # Summary table
    lines.append("## Resumen")
    lines.append("")
    lines.append("| Canal | Mensajes | Hilos |")
    lines.append("|-------|----------|-------|")
    for ch_name, msgs in sorted(channels.items()):
        threads = {m["thread"] for m in msgs if m["thread"]}
        lines.append(f"| `{ch_name}` | {len(msgs)} | {len(threads)} |")
    lines.append("")

    # Per channel
    for ch_name, msgs in sorted(channels.items()):
        lines.append(f"## Canal: `{ch_name}`")
        lines.append("")

        # Group by thread
        threads: dict[str, list[dict]] = defaultdict(list)
        for m in msgs:
            threads[m["thread"] or "_no_thread"].append(m)

        for thread_name, thread_msgs in sorted(threads.items()):
            if thread_name != "_no_thread":
                lines.append(f"### Thread: `{thread_name}` ({len(thread_msgs)} mensajes)")
            else:
                lines.append(f"### Sin thread ({len(thread_msgs)} mensajes)")
            lines.append("")

            for m in thread_msgs:
                date_short = m["date"][:10] if len(m["date"]) >= 10 else m["date"]
                fname = m["file"].relative_to(repo_root).as_posix()
                lines.append(
                    f"- **{m['from']}** → {m['to'] or '*'} "
                    f"({m['type']}) {date_short} "
                    f"[`{fname}`] — {m['summary'][:80]}"
                )
            lines.append("")

    lines.append("---")
    lines.append(f"_Última actualización: {datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}_")
    return "\n".join(lines)


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Generate channel INDEX.md")
    parser.add_argument("path", nargs="?", default="channels")
    parser.add_argument("--output", "-o", help="Output file (default: <path>/INDEX.md)")
    args = parser.parse_args()

    channels_dir = Path(args.path)
    if not channels_dir.exists():
        print(f"Not found: {channels_dir}", file=sys.stderr)
        return 2

    # Walk up to find repo root (parent of channels/)
    repo_root = channels_dir.parent if channels_dir.name == "channels" else channels_dir

    channels = index_dir(channels_dir)
    index_md = generate_index(channels, repo_root)

    output = Path(args.output) if args.output else channels_dir / "INDEX.md"
    output.write_text(index_md, encoding="utf-8")
    print(f"Generated {output} ({sum(len(v) for v in channels.values())} messages, {len(channels)} channels)")

    return 0


if __name__ == "__main__":
    sys.exit(main())