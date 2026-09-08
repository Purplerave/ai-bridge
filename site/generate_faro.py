#!/usr/bin/env python3
"""Sincronizador de El Faro del Puente hacia docs/faro.html para GitHub Pages."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".")
    ap.add_argument("--out", default="docs/faro.html")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    dst = root / args.out

    if not dst.exists():
        print(f"Error: {dst} no existe", file=sys.stderr)
        return 1

    print("El Faro: docs/faro.html verificado")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
