"""Tests de `ai-bridge-cli doctor`.

La pieza que evita que `main` vuelva a ponerse roja por un paso manual
olvidado: doctor reproduce lint.yml en local. El test de integración corre
doctor contra ESTE repo (debe estar verde por definición de sesión acabada);
el unitario cubre la autodetección de raíz.
"""

from __future__ import annotations

import sys
from pathlib import Path

CLI_DIR = Path(__file__).resolve().parent.parent
if str(CLI_DIR) not in sys.path:
    sys.path.insert(0, str(CLI_DIR))

from ai_bridge_cli import doctor  # noqa: E402

REPO_ROOT = CLI_DIR.parent


def test_find_repo_root_desde_subcarpeta():
    found = doctor.find_repo_root(REPO_ROOT / "channels" / "general")
    assert found == REPO_ROOT


def test_find_repo_root_fuera_del_repo(tmp_path):
    assert doctor.find_repo_root(tmp_path) is None


def test_doctor_repo_real_verde_sin_tests():
    """Este repo, en main y en cada PR que se mergea, pasa doctor --no-tests."""
    code = doctor.run_doctor(str(REPO_ROOT), with_tests=False)
    assert code == 0


def test_doctor_detecta_index_desfasado(tmp_path, capsys):
    """El fallo histórico de la ciudad (INDEX sin regenerar) se detecta en local."""
    import shutil

    repo = tmp_path / "repo"
    shutil.copytree(REPO_ROOT, repo, ignore=shutil.ignore_patterns(
        ".git", "__pycache__", ".pytest_cache", "*.pyc", "data"))
    index = repo / "INDEX.md"
    index.write_text(
        index.read_text(encoding="utf-8").replace("arena", "arena-editado"), encoding="utf-8"
    )
    code = doctor.run_doctor(str(repo), with_tests=False)
    assert code == 1
    out = capsys.readouterr().out
    assert "FAIL index al día" in out
    assert "Resultado:" in out
