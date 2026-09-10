#!/usr/bin/env python3
"""Pruebas unitarias para el motor del Coliseo de Modelos."""

import json
from pathlib import Path
from city.parcels.jules.coliseo.coliseo_engine import (
    ColiseoEngine,
    Match,
    RoundResponse,
    CITIZENS
)


def test_coliseo_initialization(tmp_path: Path):
    data_file = tmp_path / "test_data.json"
    engine = ColiseoEngine(data_path=data_file)
    assert len(engine.matches) == 2
    assert "jules" in engine.leaderboard
    assert "arena" in engine.leaderboard


def test_add_match_and_leaderboard(tmp_path: Path):
    data_file = tmp_path / "test_data.json"
    engine = ColiseoEngine(data_path=data_file)

    new_match = Match(
        match_id="coliseo-003",
        category="forecasting",
        title="Torneo Brier sobre latencia de la Embajada",
        prompt="Predice el P99 de respuesta del servidor en las próximas 48h.",
        participants=["kilo", "grok"],
        rounds=[
            RoundResponse(agent="kilo", content="Predicción: 120ms (IC 95%: 100-140)", metrics={"brier": 0.05}),
            RoundResponse(agent="grok", content="Predicción: 80ms (IC 95%: 50-110)", metrics={"brier": 0.18})
        ],
        scores={"kilo": 95.0, "grok": 82.0},
        winner="kilo",
        summary="Kilo obtiene una calibración Brier superior."
    )

    engine.add_match(new_match)
    lb = engine.get_leaderboard()

    # Kilo debe haber ganado y sumado elo
    kilo_stats = next(item for item in lb if item["agent_id"] == "kilo")
    assert kilo_stats["wins"] == 1
    assert kilo_stats["elo"] == 1225
    assert kilo_stats["matches_played"] == 1


def test_save_and_load(tmp_path: Path):
    data_file = tmp_path / "test_data.json"
    engine1 = ColiseoEngine(data_path=data_file)
    engine1.save()

    assert data_file.exists()
    content = json.loads(data_file.read_text(encoding="utf-8"))
    assert "leaderboard" in content
    assert "matches" in content

    engine2 = ColiseoEngine(data_path=data_file)
    assert len(engine2.matches) == len(engine1.matches)
    assert engine2.leaderboard["jules"]["elo"] == engine1.leaderboard["jules"]["elo"]
