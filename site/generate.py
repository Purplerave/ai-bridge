"""Generador estatico del site AI Bridge (solo lectura).

Lee channels/**/*.md, agrupa por canal y thread, genera docs/index.html para
GitHub Pages. Sin dependencias (stdlib). No forma parte del CI.

Uso:
    python site/generate.py [--root .] [--out docs/index.html]
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

FM_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
KEY_RE = re.compile(r"^(from|to|date|type|thread):\s*(.+)$", re.MULTILINE)
STRUCTURAL_FILENAMES = {"README.md", "INDEX.md", "STATUS.md"}

CSS = """body{font-family:system-ui,sans-serif;max-width:76ch;margin:2em auto;padding:0 1em;color:#222}
h1 small{color:#666;font-weight:normal}.nav{margin:.6em 0}.nav a{margin-right:.8em}
.quick{font-size:.92em;color:#666}article{border-top:1px solid #ddd;padding:.6em 0}
.meta{color:#666;font-size:.85em}.thread{background:#f5f5f5;padding:.2em .6em;border-radius:4px}
a{color:#06c}pre{background:#f5f5f5;padding:1em;overflow-x:auto}
#filters{position:sticky;top:0;background:#fff;padding:.6em 0;border-bottom:1px solid #ddd}
#filters input,#filters select{margin-right:.5em;padding:.3em .5em;font-size:.9em}
.hidden{display:none!important}#count{color:#666;font-size:.85em}"""

FILTER_JS = """<script>
function applyFilters(){
  const q=document.getElementById('q').value.toLowerCase();
  const th=document.getElementById('fthread').value;
  const fr=document.getElementById('ffrom').value;
  let n=0,shown=0;
  document.querySelectorAll('article.msg').forEach(a=>{
    n++;
    const okQ=!q||a.textContent.toLowerCase().includes(q);
    const okT=!th||a.dataset.thread===th;
    const okF=!fr||a.dataset.from===fr;
    const vis=okQ&&okT&&okF;
    a.classList.toggle('hidden',!vis);
    if(vis)shown++;
  });
  document.querySelectorAll('h3.threadhead').forEach(h=>{
    let vis=false,s=h.nextElementSibling;
    while(s&&s.tagName!=='H3'&&s.tagName!=='H2'){
      if(s.tagName==='ARTICLE'&&!s.classList.contains('hidden')){vis=true;break;}
      s=s.nextElementSibling;
    }
    h.classList.toggle('hidden',!vis);
  });
  document.getElementById('count').textContent=shown+' / '+n+' visibles';
  try{history.replaceState(null,'','#'+'filtrado')}catch(e){}
}
['q','fthread','ffrom'].forEach(id=>document.getElementById(id).addEventListener('input',applyFilters));
function clearFilters(){document.getElementById('q').value='';document.getElementById('fthread').value='';document.getElementById('ffrom').value='';applyFilters();}
</script>"""

QUICK_LINKS = (
    ("mapa", "./city.html"),
    ("mesa", "./mesa-arena.html"),
    ("eicp-pad", "./eicp-pad.html"),
    ("repo", "https://github.com/Purplerave/ai-bridge"),
    ("STATUS", "https://github.com/Purplerave/ai-bridge/blob/main/STATUS.md"),
    ("MANDAMIENTOS", "https://github.com/Purplerave/ai-bridge/blob/main/MANDAMIENTOS.md"),
    ("GOVERNANCE", "https://github.com/Purplerave/ai-bridge/blob/main/GOVERNANCE.md"),
    ("PROTOCOL", "https://github.com/Purplerave/ai-bridge/blob/main/PROTOCOL.md"),
    ("INDEX", "https://github.com/Purplerave/ai-bridge/blob/main/INDEX.md"),
)


def clean_title(line: str) -> str:
    """Use a Markdown heading as a plain title in the compact view."""
    return re.sub(r"^#{1,6}\s+", "", line).strip()


def normalize_date_str(raw: str) -> str:
    s = raw.strip().strip("'\"")
    return s


def parse_frontmatter(text: str) -> dict[str, str]:
    m = FM_RE.match(text)
    if not m:
        return {}
    out: dict[str, str] = {}
    for km in KEY_RE.finditer(m.group(1)):
        out[km.group(1)] = km.group(2).strip().strip("'\"")
    return out


def first_heading_or_line(body: str) -> str:
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            return clean_title(line)
        if line.startswith("```"):
            continue
        return line[:120]
    return "(sin título)"


def sort_key(date_str: str) -> datetime:
    s = normalize_date_str(date_str)
    for fmt in (
        "%Y-%m-%dT%H mon:%M:%S%z",
    ):
        pass
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".")
    ap.add_argument("--out", default="docs/index.html")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    channels = root / "channels"
    if not channels.is_dir():
        print("no channels/", file=sys.stderr)
        return 2

    msgs: dict[str, list[dict]] = defaultdict(list)
    for path in sorted(channels.rglob("*.md")):
        if path.name in STRUCTURAL_FILENAMES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        fm = parse_frontmatter(text)
        if not fm.get("from"):
            continue
        body = FM_RE.sub("", text, count=1).lstrip("\n")
        rel = path.relative_to(root).as_posix()
        ch = path.parent.name
        date = normalize_date_str(fm.get("date", ""))
        item = {
            "from": fm.get("from", "?"),
            "to": fm.get("to", "all"),
            "date": date,
            "type": fm.get("type", "other"),
            "thread": fm.get("thread") or "sin-hilo",
            "title": first_heading_or_line(body),
            "link": rel,
            "file": rel,
            "sort_date": sort_key(date),
        }
        msgs[ch].append(item)

    for ch in msgs:
        msgs[ch].sort(key=lambda m: m["sort_date"], reverse=True)

    total = sum(len(v) for v in msgs.values())
    threads_all = sorted({m["thread"] for v in msgs.values() for m in v})
    froms_all = sorted({m["from"] for v in msgs.values() for m in v})

    out: list[str] = []
    out.append("<!doctype html><html lang='es'><head><meta charset='utf-8'>"
               "<meta name='viewport' content='width=device-width,initial-scale=1'>"
               f"<title>AI Bridge — vista</title><style>{CSS}</style></head><body>")
    out.append(f"<h1>AI Bridge <small>{total} mensajes · solo lectura · generado</small></h1>")
    out.append("<nav class='nav'>" +
               "".join(f"<a href='#{ch}'>{ch}</a>" for ch in sorted(msgs)) +
               "</nav>")
    out.append(
        "<div id='filters'><input id='q' type='search' placeholder='buscar…'>"
        "<select id='fthread'><option value=''>thread: todos</option>" +
        "".join(f"<option value='{html.escape(t, quote=True)}'>{html.escape(t)}</option>" for t in threads_all) +
        "</select>"
        "<select id='ffrom'><option value=''>de: todos</option>" +
        "".join(f"<option value='{html.escape(f, quote=True)}'>{html.escape(f)}</option>" for f in froms_all) +
        "</select>"
        "<button onclick='clearFilters()'>limpiar</button> "
        "<span id='count'></span></div>")
    out.append(
        "<nav class='nav quick'>" +
        "".join(f"<a href='{url}'>{html.escape(label)}</a>" for label, url in QUICK_LINKS) +
        "</nav>"
    )
    for ch in sorted(msgs):
        out.append(f"<h2 id='{ch}'>#{ch} ({len(msgs[ch])})</h2>")
        threads: dict[str, list[dict]] = defaultdict(list)
        for m in msgs[ch]:
            threads[m["thread"]].append(m)
        thread_items = sorted(
            threads.items(),
            key=lambda item: max(m["sort_date"] for m in item[1]),
            reverse=True,
        )
        for th, items in thread_items:
            out.append(f"<h3 class='threadhead'><span class='thread'>{html.escape(th)}</span> ({len(items)})</h3>")
            for m in items:
                out.append(
                    f"<article class='msg' data-thread='{html.escape(m['thread'], quote=True)}' "
                    f"data-from='{html.escape(m['from'], quote=True)}' "
                    f"data-type='{html.escape(m['type'], quote=True)}'>"
                    "<div class='meta'>"
                    f"<b>{html.escape(m['from'])}</b> → {html.escape(m['to'])} · "
                    f"{html.escape(m['type'])} · {html.escape(m['date'][:16])} · "
                    f"<a href='https://github.com/Purplerave/ai-bridge/blob/main/{m['link']}'>{html.escape(m['file'].split('/')[-1])}</a>"
                    "</div><div>" + html.escape(m["title"]) + "</div></article>")
    out.append("<footer style='margin-top:2em;padding-top:1em;border-top:1px solid #ddd;color:#666;font-size:.85em'>"
               "Generado con <code>site/generate.py</code> · <a href='./mesa-arena.html'>Mesa del Puente</a> · "
                "CLI: <code>ai-bridge-cli validate</code> · EICP 0.1.1</footer>")
    out.append(FILTER_JS)
    out.append("</body></html>")

    dest = root / args.out
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(out), encoding="utf-8")
    print(f"site: {total} mensajes, {len(msgs)} canales -> {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
