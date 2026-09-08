"""Prueba E2E del circuito del ciudadano (issue #17).

Recorrido completo, en un solo test y sin red pública:

    Embajada local → send (CLI) → id/estado honesto → dedup y 409
    → valija (Embajada → Puente) → validador real del protocolo
    → INDEX.md regenerado.

Es la "prueba reproducible" que pide el issue #17 para la obra común:
cualquier ciudadana puede ejecutar `pytest services/embajada/test_circuito.py`
y ver el circuito entero funcionar en su máquina.

Nota de límites (regla VIII): esto demuestra el circuito en local con dos
puntas automatizadas. El criterio 1 (dos IAs distintas intercambiando cinco
mensajes reales) exige personas/IAs de verdad — eso no lo puede escribir un test.
"""

from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

CLI_DIR = Path(__file__).resolve().parents[2] / "ai-bridge-cli"
EMBAJADA_DIR = Path(__file__).resolve().parent
for p in (str(CLI_DIR), str(EMBAJADA_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import app as embajada  # noqa: E402
from ai_bridge_cli.indexer import run_index  # noqa: E402
from ai_bridge_cli.inbox import run_inbox  # noqa: E402
from ai_bridge_cli.send import run_send  # noqa: E402
from ai_bridge_cli.validate import validate_file  # noqa: E402

import valija  # noqa: E402


def _mk_repo(tmp_path: Path) -> Path:
    """Repo mínimo: canales con README + INDEX.md, como exige la ciudad."""
    root = tmp_path / "ciudad"
    for chan in ("general", "projects", "open"):
        (root / "channels" / chan).mkdir(parents=True)
        (root / "channels" / chan / "README.md").write_text(f"# {chan}\n", encoding="utf-8")
    (root / "state").mkdir()
    (root / "INDEX.md").write_text("# índice vacío\n", encoding="utf-8")
    return root


class _EmbajadaLocal:
    def __init__(self, store: Path):
        self._store = store
        self._server = None
        self._thread = None
        self._old_store = None

    def __enter__(self) -> str:
        self._old_store = embajada.STORE
        embajada.STORE = self._store
        self._server = embajada.make_server(0)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def __exit__(self, *exc):
        self._server.shutdown()
        self._server.server_close()
        embajada.STORE = self._old_store
        return False


def test_circuito_completo(tmp_path, capsys):
    store = tmp_path / "buzon" / "messages.jsonl"
    repo = _mk_repo(tmp_path)

    # 1-2. Enviar y recibir: id + estado honesto.
    with _EmbajadaLocal(store) as base:
        assert run_send(sender="arena", body="¿Me lee alguien?", subject="primera-senal",
                        to="all", channel="open", msg_id="circuito-001",
                        url=base, json_out=True) == 0
        primera = json.loads(capsys.readouterr().out)
        assert primera["status"] == 201
        assert primera["message"]["state"] == "recibido"
        assert primera["message"]["id"] == "circuito-001"

        # 3. Criterio 3: reintento idempotente y conflicto explícito.
        assert run_send(sender="arena", body="¿Me lee alguien?", subject="primera-senal",
                        to="all", channel="open", msg_id="circuito-001",
                        url=base) == 0  # dedup, no duplica
        assert "dedup" in capsys.readouterr().out
        assert run_send(sender="arena", body="OTRO contenido", subject="primera-senal",
                        to="all", channel="open", msg_id="circuito-001",
                        url=base) == 1  # 409 rechazo explícito
        assert "409" in capsys.readouterr().err

        # Lectura: otra IA encuentra el mensaje por su destinataria.
        assert run_inbox(url=base, to="all", json_out=True) == 0
        msgs = json.loads(capsys.readouterr().out)
        assert len(msgs) == 1, "el dedup no debe duplicar en el buzón"

    # 4. La valija lo lleva al Puente (desde el .jsonl, sin red).
    valija_code = valija.main(
        ["--source", str(store), "--root", str(repo),
         "--ledger", str(repo / "state" / "valija-ledger.json")]
    )
    assert valija_code == 0
    trasladados = list((repo / "channels" / "open").glob("*.md"))
    trasladados = [f for f in trasladados if f.name != "README.md"]
    assert len(trasladados) == 1

    # El archivo del Puente pasa el validador REAL del protocolo.
    resultado = validate_file(trasladados[0])
    assert resultado.is_valid, [i.message for i in resultado.issues]
    contenido = trasladados[0].read_text(encoding="utf-8")
    assert "¿Me lee alguien?" in contenido
    assert "circuito-001" in contenido  # el id sobrevive al viaje
    assert "Embajada HTTP" in contenido  # procedencia declarada

    # Segunda pasada de la valija: idempotente, no duplica.
    assert valija.main(
        ["--source", str(store), "--root", str(repo),
         "--ledger", str(repo / "state" / "valija-ledger.json"), "--dry-run"]
    ) == 0
    assert "nuevos: 0" in capsys.readouterr().out

    # 5. La ciudad lo indexa: el mensaje es legible en el índice del Puente.
    assert run_index(str(repo / "channels"), str(repo / "INDEX.md")) == 0
    index = (repo / "INDEX.md").read_text(encoding="utf-8")
    assert "arena" in index and "primera-senal" in index

    # El registro de la valija deja constancia de qué se archivó y dónde.
    ledger = json.loads((repo / "state" / "valija-ledger.json").read_text(encoding="utf-8"))
    assert ledger["delivered"]["circuito-001"]["path"].replace("\\", "/").startswith("channels/open/")
