"""
Punto de entrada WSGI para Alwaysdata / Gunicorn / uWSGI.
Permite desplegar la Embajada AI Bridge en Alwaysdata.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add repo root to Python path
repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from services.embajada.app import application

if __name__ == "__main__":
    from services.embajada.app import run_server
    run_server()
