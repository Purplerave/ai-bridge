"""Tests del harness acuerdo-modelos. Corren con pytest o con `python test_score.py`."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import score

HERE = Path(__file__).resolve().parent
RUBRIC = json.loads((HERE / "rubric.json").read_text(encoding="utf-8"))


def _resp(**kw):
    base = {
        "ia": "test-bot",
        "date": "2026-09-10T21:00:00+00:00",
        "track": "code-review",
        "findings": [
            {"item": "cr-01", "lines": [6], "class": "seguridad",
             "note": "Concatena el nombre al SQL: inyección clásica."},
        ],
    }
    base.update(kw)
    return base


def test_rubrica_coherente():
    items = set(RUBRIC["items"])
    classes = set(RUBRIC["classes"])
    assert len(RUBRIC["defects"]) == 7
    for d in RUBRIC["defects"]:
        assert d["item"] in items, d
        assert d["class"] in classes, d
        assert d["lines"] and all(isinstance(n, int) and n >= 1 for n in d["lines"]), d


def test_respuesta_valida_pasa():
    assert score.validate_response(_resp(), RUBRIC) == []


def test_respuesta_invalida_falla():
    bad_item = _resp(findings=[
        {"item": "cr-99", "lines": [1], "class": "logica", "note": "Item que no existe aquí."}])
    assert any("desconocido" in e for e in score.validate_response(bad_item, RUBRIC))
    bad_class = _resp(findings=[
        {"item": "cr-01", "lines": [6], "class": "estilo", "note": "Clase que no está en el enum."}])
    assert any("clase" in e for e in score.validate_response(bad_class, RUBRIC))
    empty_note = _resp(findings=[
        {"item": "cr-01", "lines": [6], "class": "seguridad", "note": "corto"}])
    assert any("note" in e for e in score.validate_response(empty_note, RUBRIC))
    assert any("obligatorio" in e for e in score.validate_response({"ia": "x"}, RUBRIC))


def test_coincidencia_por_interseccion_de_lineas():
    findings = [
        {"item": "cr-02", "lines": [4, 5], "class": "concurrencia", "note": "Lee sin lock; intersección parcial."},
        {"item": "cr-03", "lines": [5], "class": "logica", "note": "Fuera del defecto: línea que no intersecta."},
    ]
    matched, unmatched = score.matched_defects(findings, RUBRIC)
    assert matched == {"cr-02-d1"}
    assert [u["item"] for u in unmatched] == ["cr-03"]


def test_un_defecto_cuenta_una_vez():
    findings = [
        {"item": "cr-01", "lines": [6], "class": "seguridad", "note": "Inyección SQL por concatenación directa."},
        {"item": "cr-01", "lines": [6, 7], "class": "seguridad", "note": "Mismo defecto, rango más amplio aún."},
    ]
    matched, _ = score.matched_defects(findings, RUBRIC)
    assert matched == {"cr-01-d1"}


def test_jaccard():
    assert score.jaccard({1, 2}, {2, 3}) == 1 / 3
    assert score.jaccard(set(), set()) == 1.0
    assert score.jaccard({1}, set()) == 0.0


def test_compute_dos_ias():
    a = _resp(ia="aaa", findings=[
        {"item": "cr-01", "lines": [6], "class": "seguridad", "note": "Inyección SQL por concatenación directa."},
        {"item": "cr-03", "lines": [3], "class": "logica", "note": "Off-by-one con página 1-based, inicio mal."},
    ])
    b = _resp(ia="bbb", findings=[
        {"item": "cr-01", "lines": [6], "class": "seguridad", "note": "SQL construido con string, parametrizar ya."},
        {"item": "cr-05", "lines": [3, 4], "class": "rendimiento", "note": "N+1 clarísimo con miles de ids distintos."},
    ])
    result = score.compute(RUBRIC, [a, b])
    assert result["n_respondentes"] == 2
    assert result["por_ia"]["aaa"]["recall"] == round(2 / 7, 3)
    assert result["por_ia"]["aaa"]["recall_por_clase"]["seguridad"] == 1.0
    # Acuerdo: coinciden en 1 de 3 hallazgos distintos → 1/3.
    assert result["acuerdo_pares"] == [{"a": "aaa", "b": "bbb", "jaccard": round(1 / 3, 3)}]
    assert result["jaccard_medio"] == round(1 / 3, 3)


def test_respuesta_piloto_arena_valida():
    data = json.loads((HERE / "respuestas" / "arena.json").read_text(encoding="utf-8"))
    assert data.get("piloto") is True
    assert score.validate_response(data, RUBRIC) == []
    matched, _ = score.matched_defects(data["findings"], RUBRIC)
    assert len(matched) == 7  # la autora acredita su propia rúbrica: esperado, por eso es piloto


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"OK {name}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {name}: {exc}")
    print(f"{len(tests) - failed}/{len(tests)} verdes")
    sys.exit(1 if failed else 0)
