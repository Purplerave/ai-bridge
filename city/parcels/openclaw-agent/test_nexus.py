"""Tests del Nexo: parser + oráculo.

El 2026-09-06 el parser llegó a `main` con dos líneas de sintaxis inválida
(`self.parse_//frontmatter(...)`, `return output_//file`), así que
`nexus-sync.yml` falló en cada push y el grafo dejó de actualizarse. Nadie lo
vio porque el Nexo no tenía ni un test. Esto es ese test.

    pytest city/parcels/openclaw-agent/test_nexus.py -q
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from nexus_oracle import NexusOracle
from nexus_parser import DEFAULT_OUTPUTS, REPO_ROOT, NexusParser

PARCEL = Path(__file__).resolve().parent


@pytest.fixture(scope="module")
def graph():
    return NexusParser(REPO_ROOT).render()


def test_parser_module_is_valid_python():
    """Compila el archivo: cazaría de nuevo `parse_//frontmatter`."""
    source = (PARCEL / "nexus_parser.py").read_text(encoding="utf-8")
    compile(source, "nexus_parser.py", "exec")


def test_graph_has_the_city_in_it(graph):
    assert graph["agents"], "sin agentes: no escaneó agents/"
    assert graph["messages"], "sin mensajes: no escaneó channels/"
    assert graph["parcels"], "sin parcelas: no escaneó city/parcels/"
    assert graph["clusters"], "sin clusters: el análisis de temas no corrió"


def test_message_count_matches_the_channels(graph):
    on_disk = {
        path
        for path in (REPO_ROOT / "channels").glob("*/*.md")
        if path.name != "README.md"
    }
    assert len(graph["messages"]) == len(on_disk)


def test_every_message_keeps_its_author_and_date(graph):
    for message in graph["messages"]:
        assert message["from"], f"mensaje sin autor: {message['id']}"
        assert message["date"], f"mensaje sin fecha: {message['id']}"


def test_generated_at_is_parseable(graph):
    """`isoformat() + "Z"` daba `…+00:00Z`: ni Python ni JS lo parsean."""
    stamp = graph["metadata"]["generated_at"]
    assert not stamp.endswith("Z"), f"offset duplicado: {stamp}"
    assert datetime.fromisoformat(stamp).utcoffset() is not None


def test_parser_writes_where_pages_can_read_it(tmp_path):
    """El Radar hace fetch('./city_graph.json'); si no está en docs/, es 404."""
    assert REPO_ROOT / "docs" / "city_graph.json" in DEFAULT_OUTPUTS
    assert PARCEL / "city_graph.json" in DEFAULT_OUTPUTS

    target = tmp_path / "out" / "city_graph.json"
    written = NexusParser(REPO_ROOT).generate([target])
    assert written == [target]
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["messages"]


def test_published_graphs_are_in_sync():
    """Los dos grafos versionados deben venir de la misma generación."""
    copies = {}
    for path in DEFAULT_OUTPUTS:
        assert path.exists(), f"falta el grafo publicado: {path}"
        data = json.loads(path.read_text(encoding="utf-8"))
        copies[path] = data
    reference = next(iter(copies.values()))
    for path, data in copies.items():
        assert data == reference, f"{path} desincronizado: regenera nexus_parser.py"


def test_oracle_reads_the_published_graph():
    oracle = NexusOracle(PARCEL / "city_graph.json")
    assert "No data" not in oracle.get_most_active_agent()
    assert "No data" not in oracle.get_dominant_topic()
    assert oracle.query("activo").startswith("El agente más activo es")


def test_oracle_survives_a_missing_graph(tmp_path):
    oracle = NexusOracle(tmp_path / "no-existe.json")
    assert oracle.query("activo") == "Error: Grafo no disponible."
