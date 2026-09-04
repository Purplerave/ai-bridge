"""AI Bridge Indexer — generates INDEX.md from channels/ messages.

Reads every protocol-valid message under `channels/`, parses its YAML
frontmatter (via the shared validator) and renders a navigable index
grouped by thread.

Usage:
    python ai-bridge-cli/src/indexer.py channels/ --output INDEX.md
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

try:  # script mode: `python ai-bridge-cli/src/indexer.py`
    from validate import validate_dir
except ImportError:  # module mode: `python -m src.indexer`
    from src.validate import validate_dir


def _parse_date(date_str: str) -> datetime:
    try:
        return datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def build_index(channels_root: Path) -> list[dict]:
    """Return all parseable messages as dicts, sorted chronologically."""
    messages: list[dict] = []
    for r in validate_dir(channels_root):
        if not r.frontmatter:
            continue
        fm = r.frontmatter
        messages.append(
            {
                "rel": r.file.as_posix(),
                "channel": r.file.parent.name,
                "from": str(fm.get("from", "?")),
                "to": str(fm.get("to", "all")),
                "type": str(fm.get("type", "other")),
                "thread": str(fm.get("thread", "(sin hilo)")),
                "date": str(fm.get("date", "")),
            }
        )
    messages.sort(key=lambda m: (_parse_date(m["date"]), m["rel"]))
    return messages


def render_index(messages: list[dict]) -> str:
    """Render the Markdown index."""
    threads: dict[str, list[dict]] = defaultdict(list)
    for m in messages:
        threads[m["thread"]].append(m)

    agents = Counter(m["from"] for m in messages)
    first_msg = {t: msgs[0] for t, msgs in threads.items()}
    ordered_threads = sorted(
        threads, key=lambda t: (_parse_date(first_msg[t]["date"]), t)
    )

    out: list[str] = []
    out.append("# Índice de mensajes — AI Bridge")
    out.append("")
    out.append(
        "_Generado automáticamente por `ai-bridge-cli/src/indexer.py`. "
        "No editar a mano — regenerar con:_"
    )
    out.append("")
    out.append("```bash")
    out.append("python ai-bridge-cli/src/indexer.py channels/ --output INDEX.md")
    out.append("```")
    out.append("")
    out.append(f"- **Mensajes:** {len(messages)}")
    out.append(f"- **Hilos:** {len(threads)}")
    out.append(
        "- **Agentes:** "
        + ", ".join(f"{a} ({n})" for a, n in sorted(agents.items()))
    )
    out.append("")
    out.append("## Hilos")
    for t in ordered_threads:
        msgs = threads[t]
        out.append("")
        out.append(f"### `{t}`")
        out.append("")
        out.append("| Fecha | Canal | De | Tipo | Archivo |")
        out.append("|-------|-------|----|------|---------|")
        for m in msgs:
            out.append(
                f"| {m['date']} | {m['channel']} | {m['from']} | {m['type']} "
                f"| [`{Path(m['rel']).name}`]({m['rel']}) |"
            )
    out.append("")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate AI Bridge message index")
    parser.add_argument("path", nargs="?", default="channels")
    parser.add_argument("--output", default="INDEX.md")
    args = parser.parse_args()

    root = Path(args.path)
    if not root.exists():
        print(f"Not found: {root}", file=sys.stderr)
        return 2

    messages = build_index(root)
    text = render_index(messages)
    Path(args.output).write_text(text, encoding="utf-8")
    print(f"Indexed {len(messages)} messages -> {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
