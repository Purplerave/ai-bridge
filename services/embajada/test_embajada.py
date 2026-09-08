import json
import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import app


def test_embajada_root_response():
    assert app.VERSION == "0.3.2"


def test_embajada_file_exists():
    app_file = Path(__file__).resolve().parent / "app.py"
    readme_file = Path(__file__).resolve().parent / "README.md"
    html_file = Path(__file__).resolve().parent / "index.html"
    assert app_file.exists()
    assert readme_file.exists()
    assert html_file.exists()
    assert "<!doctype html>" in html_file.read_text(encoding="utf-8")
