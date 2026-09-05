#!/usr/bin/env python3
"""Compatibility shim — DO NOT add code here.

The workflow currently on `main` (`.github/workflows/lint.yml`) still runs
`python ai-bridge-cli/src/validate.py channels/`, but the package now lives in
`ai_bridge_cli/`. Workflow files cannot be updated from this branch (the GitHub
App token lacks the `workflows` permission), so this shim keeps CI green until
the owner switches the workflow to `ai-bridge-cli validate channels/`.
Once that is done, delete this file and the `src/` directory.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ai_bridge_cli.validate import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
