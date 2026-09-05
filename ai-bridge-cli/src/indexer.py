#!/usr/bin/env python3
"""Compatibility shim — DO NOT add code here.

`python -m src.indexer channels/` (added on main by Grok) now delegates to the
installable package: `ai-bridge-cli index channels/ --out INDEX.md`.
Delete this file together with `src/validate.py` once nothing calls `src/`.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ai_bridge_cli.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(["index", *sys.argv[1:]]))
