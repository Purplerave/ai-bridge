"""`ai-bridge-cli doctor` — reproduce los pasos de `.github/workflows/lint.yml`
en local, en un solo comando.

`main` se ha puesto roja cuatro veces por la misma familia de descuidos
(INDEX sin regenerar, enlaces rotos, derivados sin publicar). Todo eso lo
detecta CI **después** del push; `doctor` lo detecta **antes**:

    ai-bridge-cli doctor            # todo
    ai-bridge-cli doctor --no-tests # solo las comprobaciones rápidas

Cada paso imprime ✓ / ✗ / ⊘ (omitido) y el fallo muestra la cola de la salida
real del comando. Exit 1 si algo falla. Si un paso no aplica en tu árbol
(falta docs/, no hay pytest), se omite con ⊘ y se dice por qué.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PY = sys.executable or "python3"

TEST_PATHS = [
    "ai-bridge-cli/tests",
    "eicp/test_helper.py",
    "city/parcels/arena/tests/test_integration.py",
    "city/parcels/openclaw-agent/test_nexus.py",
    "services/embajada",
    "research/acuerdo-modelos/test_score.py",
]


def find_repo_root(start: Path | None = None) -> Path | None:
    """Busca hacia arriba un directorio con INDEX.md y channels/."""
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "INDEX.md").is_file() and (candidate / "channels").is_dir():
            return candidate
    return None


def _run(cmd: list[str], root: Path, timeout: int = 300) -> tuple[int, str]:
    env = {
        **__import__("os").environ,
        "PYTHONPATH": str(root / "ai-bridge-cli")
        + __import__("os").pathsep
        + __import__("os").environ.get("PYTHONPATH", ""),
    }
    try:
        proc = subprocess.run(  # noqa: S603
            cmd, cwd=root, capture_output=True, text=True, timeout=timeout, env=env
        )
    except FileNotFoundError:
        return -1, f"comando no encontrado: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return -2, f"timeout ({timeout}s): {' '.join(cmd)}"
    tail = "\n".join((proc.stdout + proc.stderr).splitlines()[-15:])
    return proc.returncode, tail


def _has(root: Path, *parts: str) -> bool:
    return (root.joinpath(*parts)).exists()


def collect_steps(root: Path, with_tests: bool = True) -> list[tuple[str, str, list[str]]]:
    """Lista de (nombre, motivo-omitido, comando). Motivo vacío = se ejecuta."""
    steps: list[tuple[str, str, list[str]]] = [
        ("validate", "", [PY, "-m", "ai_bridge_cli.cli", "validate", "channels"]),
        (
            "index al día",
            "",
            [PY, "-m", "ai_bridge_cli.cli", "index", "channels", "--out", "INDEX.md", "--check"],
        ),
    ]
    if _has(root, "site", "generate.py") and _has(root, "docs", "index.html"):
        steps.append(("docs/index.html al día", "", _docs_index_cmd()))
    if _has(root, "site", "check_links.py"):
        steps.append(("enlaces internos", "", [PY, "site/check_links.py"]))
    if with_tests and _has(root, "ai-bridge-cli", "tests"):
        existing = [p for p in TEST_PATHS if _has(root, *p.split("/"))]
        if existing:
            steps.append(("tests", "", [PY, "-m", "pytest", *existing, "-q"]))
    if _has(root, "city", "parcels", "arena", "publicar.py"):
        steps.append(
            ("Mesa publicada al día", "", [PY, "city/parcels/arena/publicar.py", "--check"])
        )
    return steps


def _docs_index_cmd() -> list[str]:
    """Genera docs/index.html en un temporal y sale 1 si difiere del publicado."""
    return [
        PY,
        "-c",
        (
            "import pathlib, subprocess, sys, tempfile\n"
            "tmp = pathlib.Path(tempfile.mkstemp(suffix='.html')[1])\n"
            "r = subprocess.run([sys.executable, 'site/generate.py', '--root', '.',\n"
            "                    '--out', str(tmp)], capture_output=True, text=True)\n"
            "if r.returncode != 0:\n"
            "    sys.stdout.write(r.stdout + r.stderr); sys.exit(1)\n"
            "live = pathlib.Path('docs/index.html').read_text(encoding='utf-8')\n"
            "gen = tmp.read_text(encoding='utf-8')\n"
            "if live != gen:\n"
            "    print('docs/index.html desactualizado: ejecuta python site/generate.py')\n"
            "    sys.exit(1)\n"
            "print('docs/index.html coincide con la generación actual')\n"
        ),
    ]


def run_doctor(root: str | None = None, with_tests: bool = True) -> int:
    repo = find_repo_root(Path(root) if root else None)
    if repo is None:
        print(
            "error: no encuentro la raíz del repo (busco INDEX.md + channels/ hacia arriba); "
            "pasa --root",
            file=sys.stderr,
        )
        return 2
    print(f"doctor - reproduciendo lint.yml en local - raiz: {repo}")
    failures = 0
    skipped = 0
    passed = 0
    for name, skip_reason, cmd in collect_steps(repo, with_tests=with_tests):
        if skip_reason:
            print(f"  - {name}: {skip_reason} (omitido)")
            skipped += 1
            continue
        code, tail = _run(cmd, repo)
        if code == 0:
            last = tail.strip().splitlines()[-1] if tail.strip() else ""
            print(f"  OK {name}" + (f" - {last}" if last else ""))
            passed += 1
        else:
            why = "comando ausente" if code == -1 else f"exit {code}"
            print(f"  FAIL {name} ({why})")
            if tail.strip():
                for line in tail.strip().splitlines()[-12:]:
                    print(f"      {line}")
            failures += 1
    verdict = "verde: puedes pushear" if failures == 0 else f"rojo: {failures} paso(s) fallan"
    print(f"Resultado: {passed} OK - {failures} FAIL - {skipped} omitidos - {verdict}")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ai-bridge-cli doctor",
        description="Reproduce los pasos de CI (lint.yml) en local antes de pushear.",
    )
    parser.add_argument("--root", default=None, help="raíz del repo (autodetectada si no)")
    parser.add_argument(
        "--no-tests", action="store_true", help="omitir la batería de tests (más rápido)"
    )
    args = parser.parse_args(argv)
    return run_doctor(args.root, with_tests=not args.no_tests)


if __name__ == "__main__":
    sys.exit(main())
