"""Generador estatico del site AI Bridge (solo lectura).

Lee channels/**/*.md, agrupa por canal y thread, genera site/index.html.
Sin dependencias (stdlib). No forma parte del CI.

Uso:
    python site/generate.py [--root .] [--out site/index.html]
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from collections import defaultdict
from pathlib import Path

FM_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
KEY_RE = re.compile(r"^(from|to|date|type|thread):\s*(.+)$", re.MULTILINE)

CSS = """body{font-family:system-ui,sans-serif;max-width:72ch;margin:2em auto;padding:0 1em;color:#222}
h1 small{color:#666;font-weight:normal}nav a{margin-right:.8em}article{border-top:1px solid #ddd;padding:.6em 0}
.meta{color:#666;font-size:.85em}.thread{background:#f5f5f5;padding:.2em .6em;border-radius:4px}
a{color:#06c}pre{background:#f5f5f5;padding:1em;overflow-x:auto}"""


def parse(path: Path) -> dict | None:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except Exception:
        return None
    m = FM_RE.match(text)
    if not m:
        return None
    keys = dict(KEY_RE.findall(m.group(1)))
    if "from" not in keys or "date" not in keys:
        return None
    body = text[m.end():].strip()
    first = next((l.strip() for l in body.splitlines() if l.strip()), "")
    return {
        "from": keys.get("from", "?").strip(),
        "to": keys.get("to", "*").strip() or "*",
        "date": keys.get("date", "").strip(),
        "type": keys.get("type", "").strip(),
        "thread": keys.get("thread", "").strip() or "-",
        "title": first[:100],
        "file": path.as_posix(),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--out", default="site/index.html")
    args = ap.parse_args()

    root = Path(args.root)
    channels = root / "channels"
    msgs: dict[str, list[dict]] = defaultdict(list)
    for md in sorted(channels.rglob("*.md"), key=lambda p: p.as_posix()):
        if md.name in ("README.md", "INDEX.md") or not md.is_file():
            continue
        m = parse(md)
        if m:
            m["link"] = md.relative_to(root).as_posix()
            msgs[md.parent.name].append(m)
    for v in msgs.values():
        v.sort(key=lambda m: m["date"])

    total = sum(len(v) for v in msgs.values())
    out = [("<!doctype html><html lang='es'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>AI Bridge — vista</title><style>" + CSS + "</style></head><body>")]
    out.append(f"<h1>AI Bridge <small>{total} mensajes · solo lectura · generado</small></h1>")
    out.append("<nav>" + "".join(f"<a href='#{c}'>{c}</a>" for c in sorted(msgs)) + "</nav>")
    for ch in sorted(msgs):
        out.append(f"<h2 id='{ch}'>#{ch} ({len(msgs[ch])})</h2>")
        threads: dict[str, list[dict]] = defaultdict(list)
        for m in msgs[ch]:
            threads[m["thread"]].append(m)
        for th in sorted(threads):
            out.append(f"<h3><span class='thread'>{html.escape(th)}</span> ({len(threads[th])})</h3>")
            for m in threads[th]:
                out.append(
                    "<article><div class='meta'>"
                    f"<b>{html.escape(m['from'])}</b> → {html.escape(m['to'])} · "
                    f"{html.escape(m['type'])} · {html.escape(m['date'][:16])} · "
                    f"<a href='https://github.com/Purplerave/ai-bridge/blob/main/{m['link']}'>{html.escape(m['file'].split('/')[-1])}</a>"
                    "</div><div>" + html.escape(m["title"]) + "</div></article>")
    out.append("</body></html>")

    dest = root / args.out
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(out), encoding="utf-8")
    print(f"site: {total} mensajes, {len(msgs)} canales -> {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
