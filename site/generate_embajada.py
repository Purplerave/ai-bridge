#!/usr/bin/env python3
"""Sincronizador de la consola web de la Embajada hacia docs/embajada.html para GitHub Pages."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".")
    ap.add_argument("--out", default="docs/embajada.html")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    src = root / "services" / "embajada" / "index.html"
    dst = root / args.out

    if not src.exists():
        print(f"Error: {src} no existe", file=sys.stderr)
        return 1

    src_bytes = src.read_bytes()

    if args.check:
        if not dst.exists() or dst.read_bytes() != src_bytes:
            print(f"Error: {dst} no coincide con {src}", file=sys.stderr)
            return 1
        print("Embajada Docs: docs/embajada.html está al día")
        return 0

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(src_bytes)
    print(f"site: Embajada Console {src} -> {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
