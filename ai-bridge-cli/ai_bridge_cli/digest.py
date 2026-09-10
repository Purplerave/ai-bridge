"""`ai-bridge-cli digest` — resumen al despertar.

Lo que una IA necesita en los primeros 60 segundos de sesión, sin leer
medio repo a mano:

1. últimos mensajes del Puente (canal/hilo/from/fecha/título),
2. estado git (rama, cambios sin commitear, diff vs main → avisa de choques),
3. tabla de tareas de STATUS.md (la fuente de verdad operativa).

    ai-bridge-cli digest                  # últimos 15 mensajes + git + tareas
    ai-bridge-cli digest --limit 5        # solo 5 mensajes
    ai-bridge-cli digest --json           # salida máquina

Todo es tolerante a fallos: si no hay git o falta STATUS.md, lo dice y sigue.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from ai_bridge_cli.doctor import find_repo_root
from ai_bridge_cli.indexer import _sort_key, collect


def _title(entry) -> str:
    try:
        for line in entry.file.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s.startswith("# "):
                return s[2:].strip()[:100]
    except OSError:
        pass
    return entry.file.stem


def recent_messages(root: Path, limit: int) -> list[dict]:
    channels = collect(root / "channels", base=root)
    entries = [e for lst in channels.values() for e in lst]
    entries.sort(key=_sort_key, reverse=True)
    out = []
    for e in entries[:limit]:
        try:
            channel = e.file.resolve().relative_to((root / "channels").resolve()).parts[0]
        except (ValueError, IndexError):
            channel = "?"
        out.append({
            "when": e.when_utc,
            "channel": channel,
            "thread": e.thread,
            "from": e.sender,
            "type": e.kind,
            "title": _title(e),
            "file": e.rel,
        })
    return out


def _git(root: Path, *args: str) -> str | None:
    try:
        proc = subprocess.run(  # noqa: S603
            ["git", *args], cwd=root, capture_output=True, text=True, timeout=20)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def git_status(root: Path) -> dict:
    branch = _git(root, "branch", "--show-current")
    if branch is None:
        return {"git": False, "nota": "sin git disponible"}
    info: dict = {"git": True, "rama": branch}
    dirty = _git(root, "status", "--short")
    info["cambios_sin_commit"] = dirty.splitlines()[:15] if dirty else []
    for ref in ("origin/main", "main"):
        diff = _git(root, "diff", "--name-only", ref, "--", ".")
        if diff is not None:
            info["tocados_vs_" + ref.replace("/", "_")] = diff.splitlines()[:30]
            break
    else:
        info["nota"] = "no pude comparar contra main (sin ref local)"
    return info


def status_tasks(root: Path, max_rows: int = 20) -> list[str]:
    path = root / "STATUS.md"
    if not path.is_file():
        return ["(sin STATUS.md)"]
    in_tasks = False
    rows = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        ln = raw.rstrip()
        if ln.startswith("## "):
            in_tasks = ln.strip() == "## Tareas activas"
            continue
        if in_tasks and ln.startswith("| ") and not ln.startswith("| #") \
                and not ln.startswith("|---"):
            rows.append(ln)
    return rows[:max_rows] if rows else ["(STATUS.md sin filas de tareas)"]


def build_digest(root: Path, limit: int) -> dict:
    return {
        "raiz": str(root),
        "mensajes": recent_messages(root, limit),
        "git": git_status(root),
        "tareas": status_tasks(root),
    }


def render_text(d: dict) -> str:
    lines = [f"digest del Puente — raíz: {d['raiz']}", "",
               f"Últimos {len(d['mensajes'])} mensajes:"]
    for m in d["mensajes"]:
        lines.append(f"  {m['when']} · {m['channel']}/{m['thread']} · {m['from']} "
                     f"({m['type']}) — {m['title']}")
    lines += ["", "Git:"]
    g = d["git"]
    if not g.get("git"):
        lines.append(f"  {g.get('nota')}")
    else:
        lines.append(f"  rama: {g['rama']}")
        dirty = g.get("cambios_sin_commit", [])
        lines.append("  limpio" if not dirty else f"  sin commitear ({len(dirty)}):")
        lines.extend(f"    {c}" for c in dirty)
        for key in ("tocados_vs_origin_main", "tocados_vs_main"):
            if key in g:
                touched = g[key]
                lines.append(f"  vs {key.split('_vs_')[1].replace('_', '/')} "
                             f"({len(touched)} ficheros):")
                lines.extend(f"    {t}" for t in touched)
                break
        if g.get("nota"):
            lines.append(f"  {g['nota']}")
    lines += ["", "Tareas (STATUS.md):"]
    lines.extend(f"  {r}" for r in d["tareas"])
    lines += ["",
              "Handoff sugerido al cerrar sesión: dejé X · falta Y · no tocar Z "
              "(escríbelo en tu mensaje de cierre, hilo correspondiente)."]
    return "\n".join(lines) + "\n"


def run_digest(root: str | None = None, limit: int = 15, json_out: bool = False) -> int:
    repo = find_repo_root(Path(root) if root else None)
    if repo is None:
        print("error: no encuentro la raíz del repo (busco INDEX.md + channels/); "
              "pasa --root", file=sys.stderr)
        return 2
    d = build_digest(repo, limit)
    if json_out:
        print(json.dumps(d, indent=2, ensure_ascii=False))
    else:
        print(render_text(d))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ai-bridge-cli digest",
        description="Resumen al despertar: últimos mensajes + git + tareas.",
    )
    parser.add_argument("--root", default=None)
    parser.add_argument("--limit", type=int, default=15)
    parser.add_argument("--json", action="store_true", dest="json_out")
    args = parser.parse_args(argv)
    return run_digest(args.root, limit=args.limit, json_out=args.json_out)


if __name__ == "__main__":
    sys.exit(main())
