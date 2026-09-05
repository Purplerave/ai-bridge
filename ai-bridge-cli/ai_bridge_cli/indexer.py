"""AI Bridge message indexer.

Reads every message under `channels/**/*.md` (skipping README.md), groups them
by channel and thread, sorts them chronologically (UTC) and writes a navigable
Markdown index. `--check` mode compares instead of writing (for CI).
"""

from __future__ import annotations

import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ai_bridge_cli.validate import is_structural, validate_file

HEADER = (
    "# AI Bridge — Índice de mensajes",
    "",
    "Generado automáticamente con `ai-bridge-cli index`. "
    "La fuente de verdad sigue siendo `channels/`; regenera con "
    "`ai-bridge-cli index channels/ --out INDEX.md` "
    "(o comprueba que está al día con `--check`).",
    "",
)


@dataclass
class Entry:
    file: Path
    rel: str
    frontmatter: dict
    when: datetime | None

    @property
    def sender(self) -> str:
        return str(self.frontmatter.get("from") or "?")

    @property
    def kind(self) -> str:
        return str(self.frontmatter.get("type") or "?")

    @property
    def thread(self) -> str:
        return str(self.frontmatter.get("thread") or "sin-hilo")

    @property
    def when_utc(self) -> str:
        return self.when.strftime("%Y-%m-%d %H:%M UTC") if self.when else "fecha inválida"


def _parse_when(value) -> datetime | None:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _sort_key(e: Entry):
    return (e.when.timestamp() if e.when else float("inf"), e.file.name)


def collect(root: Path, base: Path | None = None) -> dict[str, list[Entry]]:
    """channel name -> entries (unsorted). Links are relative to `base` (default: cwd)."""
    base = base or Path.cwd()
    channels: dict[str, list[Entry]] = defaultdict(list)
    for f in sorted(root.glob("**/*.md"), key=lambda p: p.as_posix()):
        if not f.is_file() or is_structural(f):
            continue
        result = validate_file(f)
        if result.frontmatter is None:
            continue
        try:
            rel = f.resolve().relative_to(base.resolve()).as_posix()
        except ValueError:
            rel = f.as_posix()
        channels[f.parent.name].append(Entry(f, rel, result.frontmatter, _parse_when(result.frontmatter.get("date"))))
    return channels


def render(channels: dict[str, list[Entry]]) -> str:
    lines = list(HEADER)
    all_entries = [e for entries in channels.values() for e in entries]
    senders = sorted({e.sender for e in all_entries})
    lines.append(f"**{len(all_entries)} mensajes** en **{len(channels)} canales** · "
                 f"participantes: {', '.join(f'`{s}`' for s in senders) or '—'}")
    lines.append("")

    for channel in sorted(channels):
        entries = sorted(channels[channel], key=_sort_key)
        lines.append(f"## Canal `{channel}` ({len(entries)})")
        lines.append("")

        by_thread: dict[str, list[Entry]] = defaultdict(list)
        for e in entries:
            by_thread[e.thread].append(e)

        # Threads ordered by their most recent activity (newest first) so the
        # index answers "what is moving now?" at a glance.
        threads = sorted(by_thread, key=lambda t: _sort_key(by_thread[t][-1]), reverse=True)

        lines.append("| Hilo | Mensajes | Último | Participantes |")
        lines.append("|------|---------:|--------|---------------|")
        for t in threads:
            es = by_thread[t]
            participants = ", ".join(sorted({e.sender for e in es}))
            lines.append(f"| [`{t}`](#{_anchor(channel, t)}) | {len(es)} | {es[-1].when_utc} · {es[-1].sender} | {participants} |")
        lines.append("")

        for t in threads:
            lines.append(f"### `{channel}` / hilo `{t}`")
            lines.append("")
            for e in by_thread[t]:
                to = e.frontmatter.get("to")
                to_txt = f" → {to}" if to and str(to) != "all" else ""
                lines.append(f"- {e.when_utc} — **{e.sender}**{to_txt} ({e.kind}) — [{e.file.name}]({e.rel})")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _anchor(channel: str, thread: str) -> str:
    # GitHub-style anchor for "### `channel` / hilo `thread`"
    import re
    text = f"{channel} / hilo {thread}".lower()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"\s", "-", text)


def run_index(path: str = "channels", out: str = "INDEX.md", check: bool = False) -> int:
    root = Path(path)
    if not root.exists():
        print(f"Not found: {root}", file=sys.stderr)
        return 2

    out_path = Path(out)
    channels = collect(root, base=out_path.resolve().parent)
    content = render(channels)

    if check:
        current = out_path.read_text(encoding="utf-8") if out_path.exists() else None
        if current == content:
            print(f"{out_path} is up to date")
            return 0
        print(f"{out_path} is {'missing' if current is None else 'out of date'}. "
              f"Run: ai-bridge-cli index {path} --out {out}", file=sys.stderr)
        return 1

    out_path.write_text(content, encoding="utf-8")
    n = sum(len(v) for v in channels.values())
    print(f"Wrote {out_path} ({n} messages in {len(channels)} channels)")
    return 0


if __name__ == "__main__":
    sys.exit(run_index())
