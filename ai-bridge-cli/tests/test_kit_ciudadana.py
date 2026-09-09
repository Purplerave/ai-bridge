"""Kit A1: las 5 páginas y 3 plantillas existen y se enlazan."""
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
KIT = REPO / "docs" / "kit"
SRC = REPO / "city" / "kit-ciudadana"

PAGES = ("index.html", "prompts.html", "comparar.html", "privacidad.html", "no-fiarse.html")
PLANTILLAS = ("prompts.md", "comparacion.csv", "privacidad.md")


def test_cinco_paginas_y_css():
    assert (KIT / "kit.css").is_file()
    for name in PAGES:
        html = (KIT / name).read_text(encoding="utf-8")
        assert "<!doctype html>" in html.lower()
        assert 'href="./kit.css"' in html
        assert "Kit" in html or "kit" in html


def test_plantillas():
    for name in PLANTILLAS:
        path = SRC / "plantillas" / name
        assert path.is_file(), path
        assert path.stat().st_size > 80


def test_hub_enlaza_las_cuatro_y_plantillas():
    hub = (KIT / "index.html").read_text(encoding="utf-8")
    for name in PAGES[1:]:
        assert f"./{name}" in hub
    assert "prompts.md" in hub
    assert "comparacion.csv" in hub
    assert "privacidad.md" in hub


def test_no_fiarse_es_sello_arena():
    text = (KIT / "no-fiarse.html").read_text(encoding="utf-8")
    assert "Arena" in text
    assert "NO fiarse" in text or "No fiarse" in text


def test_readme_fuente():
    readme = (SRC / "README.md").read_text(encoding="utf-8")
    assert "docs/kit/" in readme
    assert "MVP" in readme
