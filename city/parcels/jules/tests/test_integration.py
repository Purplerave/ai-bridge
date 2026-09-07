import pytest
from pathlib import Path
import sys

jules_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(jules_dir))
import publicar

def test_publicar_check():
    assert publicar.main() == 0

def test_inspector_html_valid():
    inspector_path = Path(__file__).resolve().parents[1] / "inspector.html"
    assert inspector_path.exists()
    content = inspector_path.read_text(encoding="utf-8")
    assert "<!doctype html>" in content
    assert "El Inspector del Puente" in content
    assert "PROTOCOL.md" in content
