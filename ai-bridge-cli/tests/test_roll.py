"""Tests de `ai-bridge-cli roll` (bitácora de tiradas de la partida).

El ledger se escribe en una ruta temporal en cada test: jamás se toca
`state/rolls-ledger.json` del repo.
"""

from __future__ import annotations

import json
from datetime import datetime

from ai_bridge_cli.roll import _load, _roll, run_list, run_roll

from pathlib import Path


def _ledger(tmp_path) -> Path:
    return tmp_path / "rolls-test.json"


def test_roll_requiere_ia(capsys, tmp_path):
    assert run_roll(ia="", ledger=_ledger(tmp_path)) == 2
    err = capsys.readouterr().err
    assert "falta la IA" in err


def test_roll_ia_desconocida_rechazada(capsys, tmp_path):
    assert run_roll(ia="chatgpt", ledger=_ledger(tmp_path)) == 2
    err = capsys.readouterr().err
    assert "no reconocida" in err


def test_roll_declarada_se_registra(capsys, tmp_path):
    ledger = _ledger(tmp_path)
    assert run_roll(ia="grok", resultado=12, dados="1d20",
                    motivo="Persuasión", ledger=ledger) == 0
    rows = _load(ledger)
    assert len(rows) == 1
    assert rows[0]["ia"] == "grok"
    assert rows[0]["resultado"] == 12
    assert rows[0]["origen"] == "declarada"
    assert "." in rows[0]["date"] or "T" in rows[0]["date"]


def test_roll_tirada_script_dentro_de_rango(capsys, tmp_path):
    ledger = _ledger(tmp_path)
    assert run_roll(ia="kilo", dados="4d6", ledger=ledger) == 0
    rows = _load(ledger)
    assert len(rows) == 1
    resultado = rows[0]["resultado"]
    assert 4 <= resultado <= 24
    assert rows[0]["origen"] == "tirada_script"


def test_roll_sum_4d20_no_excede_maximo():
    for _ in range(20):
        valor = _roll("4d20")
        assert 4 <= valor <= 80


def test_roll_dados_invalidos(capsys, tmp_path):
    assert run_roll(ia="arena", dados="d20", ledger=_ledger(tmp_path)) == 2
    err = capsys.readouterr().err
    assert "dados inválido" in err


def test_roll_acumula_historial(capsys, tmp_path):
    ledger = _ledger(tmp_path)
    assert run_roll(ia="grok", resultado=5, dados="1d20", ledger=ledger) == 0
    assert run_roll(ia="kilo", resultado=17, dados="1d20", ledger=ledger) == 0
    capsys.readouterr()
    assert run_list(ledger=ledger) == 0
    out = capsys.readouterr().out
    assert "grok" in out and "5" in out and "kilo" in out and "17" in out


def test_roll_list_vacio(capsys, tmp_path):
    assert run_list(ledger=_ledger(tmp_path)) == 1
    assert "vacío" in capsys.readouterr().err