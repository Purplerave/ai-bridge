#!/usr/bin/env python3
import sys
from pathlib import Path

def main() -> int:
    parcels_dir = Path(__file__).resolve().parent
    repo_root = parcels_dir.parents[2]
    src = parcels_dir / "inspector.html"
    dst = repo_root / "docs" / "inspector-jules.html"

    if not src.exists():
        print(f"Error: {src} no existe", file=sys.stderr)
        return 1

    src_bytes = src.read_bytes()

    if "--check" in sys.argv:
        if not dst.exists() or dst.read_bytes() != src_bytes:
            print("Error: docs/inspector-jules.html no coincide con city/parcels/jules/inspector.html", file=sys.stderr)
            return 1
        print("Inspector Jules: docs/inspector-jules.html está al día")
        return 0

    dst.write_bytes(src_bytes)
    print(f"Copiado {src} -> {dst}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
