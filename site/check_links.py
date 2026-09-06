#!/usr/bin/env python3
"""Comprueba que los enlaces internos de la ciudad no apunten al vacío.

La ciudad ya se rompió tres veces por esto en dos días: `/docs/plaza.html` en un
site cuya raíz *es* `docs/`, `../docs/index.html` desde una parcela (que resuelve
a `city/docs/`), y `fetch('./city_graph.json')` contra un archivo que no estaba
publicado. Ninguno daba error en CI; se veían al abrir la página.

    python site/check_links.py           # informe + exit 1 si hay roturas
    python site/check_links.py --quiet   # solo las roturas

Solo mira rutas locales: nada de red, nada de dependencias.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

REPO = Path(__file__).resolve().parent.parent

# GitHub Pages sirve docs/ como raíz del site. Un enlace absoluto a /ai-bridge/
# se resuelve contra docs/, no contra la raíz del repo.
PAGES_ROOT = REPO / "docs"
PAGES_PREFIX = "/ai-bridge/"

ATTR_RE = re.compile(r"""(?:href|src)\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
FETCH_RE = re.compile(r"""fetch\(\s*['"]([^'"]+)['"]""")

SKIP_SCHEMES = {"http", "https", "mailto", "data", "javascript", "tel"}


def targets_in(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return ATTR_RE.findall(text) + FETCH_RE.findall(text)


def resolve(source: Path, target: str) -> Path | None:
    """Devuelve la ruta que debería existir, o None si no hay que comprobarla."""
    parsed = urlparse(target)
    if parsed.scheme in SKIP_SCHEMES or target.startswith("#") or not target.strip():
        return None

    relative = unquote(parsed.path)
    if not relative:
        return None

    if relative.startswith(PAGES_PREFIX):
        return PAGES_ROOT / relative[len(PAGES_PREFIX):]
    if relative.startswith("/"):
        return PAGES_ROOT / relative.lstrip("/")

    base = source.parent
    candidate = (base / relative).resolve()
    if relative.endswith("/"):
        candidate = candidate / "index.html"
    return candidate


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--quiet", action="store_true", help="Solo mostrar roturas.")
    args = cli.parse_args()

    pages = sorted(
        path
        for path in list(PAGES_ROOT.glob("*.html"))
        + list((REPO / "city" / "parcels").glob("*/*.html"))
        + [REPO / "index.html"]
        if path.exists()
    )

    broken: list[tuple[Path, str, Path]] = []
    checked = 0

    for page in pages:
        for target in targets_in(page):
            destination = resolve(page, target)
            if destination is None:
                continue
            checked += 1
            if not destination.exists():
                broken.append((page, target, destination))

    if not args.quiet:
        print(f"Enlaces locales comprobados: {checked} en {len(pages)} páginas")

    for page, target, destination in broken:
        print(
            f"ROTO  {page.relative_to(REPO)} -> {target}"
            f"  (no existe: {destination})"
        )

    if broken:
        print(f"\n{len(broken)} enlace(s) roto(s).")
        return 1

    if not args.quiet:
        print("Sin enlaces internos rotos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
