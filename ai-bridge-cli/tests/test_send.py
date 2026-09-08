"""Tests de `ai-bridge-cli send` e `inbox` contra una Embajada real en local.

Levanta `services/embajada/app.make_server(0)` en un hilo con almacén
temporal: la CLI habla HTTP de verdad, sin tocar la Embajada pública
(nunca se usa la URL por defecto en tests).
"""

from __future__ import annotations

import json
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

CLI_DIR = Path(__file__).resolve().parent.parent
EMBAJADA_DIR = CLI_DIR.parent / "services" / "embajada"
for p in (str(CLI_DIR), str(EMBAJADA_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import app as embajada  # noqa: E402
from ai_bridge_cli.inbox import run_inbox  # noqa: E402
from ai_bridge_cli.send import run_send  # noqa: E402


@pytest.fixture()
def embajada_local(tmp_path, monkeypatch):
    """Embajada real en un puerto efímero, con almacén temporal."""
    monkeypatch.setattr(embajada, "STORE", tmp_path / "messages.jsonl")
    server = embajada.make_server(0)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    server.server_close()


def test_send_recibido_201(embajada_local, capsys):
    code = run_send(sender="arena", body="hola ciudad", subject="prueba-send",
                    url=embajada_local)
    assert code == 0
    out = capsys.readouterr().out
    assert "201" in out and "recibido" in out
    assert "id:" in out and "estado: recibido" in out


def test_send_json_incluye_estado(embajada_local, capsys):
    assert run_send(sender="a", body="x", url=embajada_local, json_out=True) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["status"] == 201
    assert data["message"]["state"] == "recibido"


def test_send_dedup_mismo_id_mismo_cuerpo(embajada_local, capsys):
    assert run_send(sender="a", body="hola", url=embajada_local,
                    msg_id="reintento-1") == 0
    capsys.readouterr()
    assert run_send(sender="a", body="hola", url=embajada_local,
                    msg_id="reintento-1") == 0
    out = capsys.readouterr().out
    assert "dedup" in out


def test_send_mismo_id_distinto_cuerpo_falla(embajada_local, capsys):
    assert run_send(sender="a", body="uno", url=embajada_local,
                    msg_id="choque-1") == 0
    capsys.readouterr()
    assert run_send(sender="a", body="dos", url=embajada_local,
                    msg_id="choque-1") == 1
    err = capsys.readouterr().err
    assert "409" in err and "id_exists" in err


def test_send_cuerpo_vacio_rechazado_en_cliente(embajada_local):
    assert run_send(sender="a", body="   ", url=embajada_local) == 2


def test_send_url_inaccesible_da_alternativa(capsys):
    # Puerto cerrado: conexión rechazada inmediata.
    code = run_send(sender="a", body="x", url="http://127.0.0.1:9", timeout=2)
    assert code == 2
    err = capsys.readouterr().err
    assert "ai-bridge-cli new" in err


def test_inbox_lista_y_filtra(embajada_local, capsys):
    run_send(sender="grok", body="para todos", url=embajada_local)
    run_send(sender="muse", body="para arena", to="arena", url=embajada_local)
    capsys.readouterr()

    assert run_inbox(url=embajada_local) == 0
    todo = capsys.readouterr().out
    assert "grok" in todo and "muse" in todo

    assert run_inbox(url=embajada_local, to="arena") == 0
    filtrado = capsys.readouterr().out
    assert "muse" in filtrado and "grok" not in filtrado


def test_inbox_json(embajada_local, capsys):
    run_send(sender="a", body="hola", url=embajada_local)
    capsys.readouterr()
    assert run_inbox(url=embajada_local, json_out=True, limit=5) == 0
    rows = json.loads(capsys.readouterr().out)
    assert rows and rows[-1]["body"] == "hola"


def test_inbox_url_inaccesible(capsys):
    assert run_inbox(url="http://127.0.0.1:9", timeout=2) == 2
