#!/usr/bin/env python3
"""Generador y verificador del grafo El Nexo del Puente."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".")
    ap.add_argument("--out", default="docs/nexus.html")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    root = Path(args.root)
    src = root / "city" / "parcels" / "jules" / "nexus.html"
    dst = root / args.out

    if not src.exists():
        print(f"Error: {src} no existe", file=sys.stderr)
        return 1

    src_bytes = src.read_bytes()

    if args.check:
        if not dst.exists() or dst.read_bytes() != src_bytes:
            print(f"Error: {dst} no coincide con {src}", file=sys.stderr)
            return 1
        print("El Nexo: docs/nexus.html está al día")
        return 0

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(src_bytes)
    print(f"site: El Nexo {src} -> {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
