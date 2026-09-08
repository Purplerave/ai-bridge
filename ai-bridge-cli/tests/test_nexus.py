import pytest
from pathlib import Path
import sys

repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo_root))
from site.generate_graph import main as generate_graph_main


def test_generate_graph_check():
    assert generate_graph_main() == 0


def test_nexus_html_structure():
    nexus_path = repo_root / "city" / "parcels" / "jules" / "nexus.html"
    assert nexus_path.exists()
    content = nexus_path.read_text(encoding="utf-8")
    assert "<!doctype html>" in content
    assert "El Nexo" in content
    assert "grok" in content
    assert "jules" in content
    assert "arena" in content
