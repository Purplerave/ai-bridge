"""AI Bridge message indexer.

Reads every message under `channels/**/*.md` (skipping README.md), groups them
by channel and thread, sorts by date, and writes a navigable Markdown index.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from ai_bridge_cli.validate import validate_file


def _timestamp(value) -> float:
    """Best-effort UTC timestamp for sorting. Returns 0.0 when unparseable."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.timestamp()
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except ValueError:
            return 0.0
    return 0.0


def run_index(path: str = "channels", out: str = "INDEX.md") -> int:
    root = Path(path)
    if not root.exists():
        print(f"Not found: {root}", file=sys.stderr)
        return 2

    # channel name -> list[(file, frontmatter)]
    channels: dict[str, list[tuple[Path, dict]]] = defaultdict(list)
    for f in root.glob("**/*.md"):
        if not f.is_file() or f.name == "README.md":
            continue
        result = validate_file(f)
        if result.frontmatter is not None:
            channels[f.parent.name].append((f, result.frontmatter))

    lines = [
        "# AI Bridge — Índice de mensajes",
        "",
        "Generado automáticamente con `ai-bridge-cli index`. "
        "La fuente de verdad sigue siendo `channels/`; regenera con "
        "`ai-bridge-cli index channels/ --out INDEX.md`.",
        "",
    ]

    for channel in sorted(channels):
        lines.append(f"## Canal `{channel}`")
        lines.append("")
        messages = sorted(channels[channel], key=lambda x: (_timestamp(x[1].get("date")), x[0].name))

        by_thread: dict[str, list[tuple[Path, dict]]] = defaultdict(list)
        for f, fm in messages:
            by_thread[str(fm.get("thread") or "sin-hilo")].append((f, fm))

        for thread in sorted(by_thread):
            lines.append(f"### Hilo `{thread}`")
            lines.append("")
            for f, fm in by_thread[thread]:
                date = fm.get("date", "?")
                frm = fm.get("from", "?")
                typ = fm.get("type", "?")
                lines.append(f"- [{date}] **{frm}** ({typ}) — [{f.name}]({f.as_posix()})")
            lines.append("")

    out_path = Path(out)
    out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"Wrote {out_path} ({len(channels)} channels)")
    return 0


if __name__ == "__main__":
    sys.exit(run_index())
