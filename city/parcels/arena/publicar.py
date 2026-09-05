#!/usr/bin/env python3
"""Publish the standalone table to docs/; source stays in Arena's parcel.

    python city/parcels/arena/publicar.py
    python city/parcels/arena/publicar.py --check

No network, timestamp injection or third-party dependencies.
"""

from __future__ import annotations

import argparse
from pathlib import Path

SOURCE = Path(__file__).resolve().with_name("index.html")
DESTINATION = SOURCE.parents[3] / "docs" / "mesa-arena.html"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare without writing")
    args = parser.parse_args(argv)
    source = SOURCE.read_bytes()
    if args.check:
        if DESTINATION.is_file() and DESTINATION.read_bytes() == source:
            print("Mesa del Puente: docs/mesa-arena.html está al día")
            return 0
        print("Mesa del Puente: falta regenerar docs/mesa-arena.html")
        return 1
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    DESTINATION.write_bytes(source)
    print("Mesa del Puente: copia idéntica en docs/mesa-arena.html (no publicada en remoto)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
