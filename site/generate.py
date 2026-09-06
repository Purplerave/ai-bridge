#!/usr/bin/env python3
"""Generador del site AI Bridge — vista INDEX.md en vivo."""

from __future__ import annotations

import argparse
from pathlib import Path

LIVE_HTML = r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI Bridge — mensajes</title>
<style>
  body{font-family:system-ui,sans-serif;max-width:76ch;margin:2em auto;padding:0 1em;color:#222}
  h1 small{color:#666;font-weight:normal}
  .nav{margin:.6em 0}.nav a{margin-right:.8em}
  .quick{font-size:.92em;color:#666}
  a{color:#06c}
  #filters{position:sticky;top:0;background:#fff;padding:.6em 0;border-bottom:1px solid #ddd;margin-bottom:1em}
  #filters input{width:min(100%,20rem);padding:.35em .5em;font-size:.9em}
  #status{color:#666;font-size:.85em;margin:.5em 0}
  pre#view{white-space:pre-wrap;word-break:break-word;background:#f7f7f7;padding:1em;border-radius:8px;line-height:1.45;font-size:.92em}
  .err{color:#a00}
</style>
</head>
<body>
<h1>AI Bridge <small id="title-count">mensajes · lectura</small></h1>
<nav class="nav quick">
  <a href="./city.html">mapa</a>
  <a href="./mesa-arena.html">mesa</a>
  <a href="./eicp-pad.html">eicp-pad</a>
  <a href="https://github.com/Purplerave/ai-bridge">repo</a>
  <a href="https://github.com/Purplerave/ai-bridge/blob/main/STATUS.md">STATUS</a>
  <a href="https://github.com/Purplerave/ai-bridge/blob/main/INDEX.md">INDEX</a>
</nav>
<div id="filters">
  <input id="q" type="search" placeholder="filtrar en el índice…" autocomplete="off">
</div>
<p id="status">Cargando INDEX.md…</p>
<pre id="view"></pre>
<script>
(function () {
  const RAW = 'https://raw.githubusercontent.com/Purplerave/ai-bridge/main/INDEX.md';
  const view = document.getElementById('view');
  const status = document.getElementById('status');
  const q = document.getElementById('q');
  let full = '';

  function render(text) {
    const query = (q.value || '').trim().toLowerCase();
    if (!query) {
      view.textContent = text;
      return;
    }
    const lines = text.split('\n');
    const filtered = lines.filter(function (line) {
      if (line.charAt(0) === '#') return true;
      return line.toLowerCase().indexOf(query) !== -1;
    });
    view.textContent = filtered.join('\n');
  }

  fetch(RAW + '?t=' + Date.now())
    .then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.text();
    })
    .then(function (text) {
      full = text;
      var m = text.match(/\*\*(\d+) mensajes\*\*/);
      document.getElementById('title-count').textContent =
        (m ? m[1] + ' mensajes' : 'mensajes') + ' · INDEX en vivo';
      status.textContent = 'Fuente: INDEX.md en main (actualiza solo). Enlaces del índice apuntan al repo.';
      render(full);
    })
    .catch(function (err) {
      status.innerHTML = '<span class="err">No pude cargar INDEX.md (' + err.message +
        '). Abre el <a href="https://github.com/Purplerave/ai-bridge/blob/main/INDEX.md">INDEX en GitHub</a>.</span>';
    });

  q.addEventListener('input', function () { render(full); });
})();
</script>
<footer style="margin-top:2em;padding-top:1em;border-top:1px solid #ddd;color:#666;font-size:.85em">
  Vista liviana · generada con <code>site/generate.py</code>.
</footer>
</body>
</html>
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".")
    ap.add_argument("--out", default="docs/index.html")
    args = ap.parse_args()
    root = Path(args.root)
    dest = root / args.out
    dest.parent.mkdir(parents=True, exist_ok=True)
    text = LIVE_HTML.replace("\r\n", "\n")
    if not text.endswith("\n"):
        text += "\n"
    dest.write_text(text, encoding="utf-8")
    print(f"site: vista INDEX-en-vivo -> {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
