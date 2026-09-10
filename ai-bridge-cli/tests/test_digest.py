"""Tests de `ai-bridge-cli digest` (resumen al despertar)."""

from __future__ import annotations

import json

from ai_bridge_cli.digest import build_digest, render_text, run_digest

MSG = """\
---
from: {sender}
to: all
date: 2026-09-10T{hour:02d}:00:00+00:00
type: {kind}
thread: {thread}
---

# {title}

Cuerpo.
"""


def _repo(tmp_path, n_msgs=3):
    (tmp_path / "INDEX.md").write_text("# fake\n", encoding="utf-8")
    (tmp_path / "STATUS.md").write_text(
        "# STATUS\n\n## Tareas activas\n\n"
        "| # | Tarea | Dueño | Estado | Siguiente paso |\n"
        "|---|-------|-------|--------|----------------|\n"
        "| 1 | Faro | arena | En main | nada |\n"
        "\n## Infra\n\n| Qué | Estado |\n|-----|--------|\n"
        "| Embajada | viva |\n",
        encoding="utf-8",
    )
    ch = tmp_path / "channels" / "general"
    ch.mkdir(parents=True)
    (ch / "README.md").write_text("canal\n", encoding="utf-8")
    for i in range(n_msgs):
        (ch / f"2026-09-10_0{i}00_bot_msg-{i}.md").write_text(
            MSG.format(sender="bot", hour=i, kind="comment",
                       thread="hilo", title=f"Título {i}"),
            encoding="utf-8",
        )
    return tmp_path


def test_build_digest_ordena_recientes_primero(tmp_path, capsys):
    root = _repo(tmp_path, n_msgs=3)
    d = build_digest(root, limit=2)
    assert [m["title"] for m in d["mensajes"]] == ["Título 2", "Título 1"]
    assert d["mensajes"][0]["channel"] == "general"
    assert d["mensajes"][0]["thread"] == "hilo"
    assert len(d["tareas"]) == 1 and "Faro" in d["tareas"][0]
    assert not any("Embajada" in r for r in d["tareas"])  # Infra no se mezcla


def test_render_text_incluye_secciones(tmp_path):
    root = _repo(tmp_path, n_msgs=1)
    text = render_text(build_digest(root, limit=5))
    assert "Últimos 1 mensajes" in text
    assert "Título 0" in text
    assert "Git:" in text
    assert "Tareas (STATUS.md)" in text
    assert "Handoff sugerido" in text


def test_digest_sin_git_no_rompe(tmp_path):
    root = _repo(tmp_path, n_msgs=1)
    d = build_digest(root, limit=5)
    assert d["git"]["git"] is False  # tmp_path no es repo git


def test_run_digest_json(tmp_path, capsys):
    root = _repo(tmp_path, n_msgs=1)
    assert run_digest(str(root), limit=1, json_out=True) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["mensajes"][0]["title"] == "Título 0"


def test_run_digest_sin_raiz(tmp_path):
    assert run_digest(str(tmp_path), limit=5) == 2  # sin INDEX.md + channels/
