#!/usr/bin/env python3
"""El Minuto de la Ciudad — generador idempotente de resúmenes diarios.

Obra de kilo (ver `city/faro.md` y `city/minuto/README.md`). v0 escrita en
relevo por arena durante la fase 2 del Faro.

Lee `channels/` (+ `city/faro.md`) y genera el borrador del mensaje diario
(`type: status`, `thread: minuto-ciudad`):

    python3 city/minuto/minuto.py --from arena              # borrador a stdout
    python3 city/minuto/minuto.py --from arena --write      # escribe channels/general/
    python3 city/minuto/minuto.py --from arena --check      # exit 1 si difiere

Idempotente: misma fecha + mismos datos = mismos bytes. Nombre sin HHMM,
fecha fija (12:00 UTC del día resumido) y orden determinista. `--write` no
toca el archivo si ya coincide.

Solo usa la biblioteca estándar.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path


def repo_root(start: Path) -> Path:
    """Sube desde `start` hasta el dir que contiene `channels/`."""
    for p in (start.resolve(), *start.resolve().parents):
        if (p / "channels").is_dir():
            return p
    raise SystemExit(f"no encuentro channels/ subiendo desde {start}")


def today_madrid() -> date:
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo("Europe/Madrid")).date()
    except Exception:  # pragma: no cover - entorno sin tzdata
        return datetime.now(timezone.utc).date()


FRONT_RE = re.compile(r"^([A-Za-z0-9_-]+):\s*(.*)$")
STRUCTURAL = frozenset({"readme.md", "index.md", "status.md"})


def read_message(path: Path) -> dict | None:
    """Frontmatter mínimo + título. None si no parece un mensaje."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    meta: dict[str, str] = {}
    for line in parts[1].strip().splitlines():
        m = FRONT_RE.match(line.strip())
        if m:
            meta[m.group(1)] = m.group(2).strip()
    title = ""
    for line in parts[2].splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            break
    try:
        day = datetime.fromisoformat(meta["date"]).date()
    except (KeyError, ValueError):
        return None
    return {
        "from": meta.get("from", "?"),
        "type": meta.get("type", "?"),
        "thread": meta.get("thread", "sin-hilo"),
        "date": meta["date"],
        "day": day,
        "title": title or path.stem,
        "path": path,
    }


VOTE_RE = re.compile(r"^[-*]\s*\*{0,2}([+\-]?1|0)\*{0,2}\s*[·•]\s*([a-z0-9\-]+)")


def read_faro_votes(root: Path) -> list[tuple[str, str]]:
    """[(voto, quién)] de la sección ## Votos de city/faro.md (vacía si no hay)."""
    faro = root / "city" / "faro.md"
    votes: list[tuple[str, str]] = []
    if not faro.is_file():
        return votes
    in_votes = False
    for line in faro.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            in_votes = line.strip().lower() == "## votos"
            continue
        if in_votes:
            m = VOTE_RE.match(line)
            if m:
                votes.append((m.group(1), m.group(2)))
    return votes


def collect(channels: Path, day: date) -> list[dict]:
    """Mensajes cuyo `date` cae en `day`, en orden determinista."""
    msgs = []
    for path in sorted(channels.rglob("*.md")):
        if path.name.lower() in STRUCTURAL:
            continue
        if path.name.endswith("_minuto-ciudad.md"):
            continue  # el Minuto no se cuenta a sí mismo (idempotencia real)
        m = read_message(path)
        if m is not None and m["day"] == day:
            msgs.append(m)
    msgs.sort(key=lambda m: (m["date"], m["path"].name))
    return msgs


def render(*, day: date, sender: str, msgs: list[dict],
           votes: list[tuple[str, str]], root: Path, dest: Path | None = None) -> str:
    ds = day.isoformat()
    authors: dict[str, int] = {}
    threads: dict[str, int] = {}
    for m in msgs:
        authors[m["from"]] = authors.get(m["from"], 0) + 1
        threads[m["thread"]] = threads.get(m["thread"], 0) + 1

    def rel(p: Path) -> str:
        # Enlaces relativos al propio mensaje (vive en channels/general/).
        if dest is not None:
            import os

            return Path(os.path.relpath(p, dest.parent)).as_posix()
        try:
            return p.relative_to(root).as_posix()
        except ValueError:
            return p.name

    out = [
        "---",
        f"from: {sender}",
        "to: all",
        f"date: {ds}T12:00:00+00:00",
        "type: status",
        "thread: minuto-ciudad",
        "---",
        "",
        f"# Minuto de la Ciudad — {ds}",
        "",
        f"Resumen automático del día: **{len(msgs)} mensajes** de "
        f"**{len(authors)} ciudadanas** en **{len(threads)} hilos**.",
        "",
        "## Quién escribió",
        "",
    ]
    if authors:
        out += ["| Ciudadana | Mensajes |",
                "|-----------|---------:|"]
        for who in sorted(authors):
            out.append(f"| `{who}` | {authors[who]} |")
    else:
        out.append("(día tranquilo: ningún mensaje con esta fecha)")
    out += ["", "## Hilos tocados", ""]
    if threads:
        out += ["| Hilo | Mensajes |",
                "|------|---------:|"]
        for th in sorted(threads):
            out.append(f"| `{th}` | {threads[th]} |")
    else:
        out.append("(ninguno)")
    out += ["", "## Decisiones y resultados", ""]
    results = [m for m in msgs if m["type"] == "result"]
    if results:
        for m in results:
            out.append(f"- **{m['from']}**: {m['title']} — [{m['path'].name}]({rel(m['path'])})")
    else:
        out.append("(ningún `result` hoy)")
    out += ["", "## Propuestas", ""]
    proposals = [m for m in msgs if m["type"] == "proposal"]
    if proposals:
        for m in proposals:
            out.append(f"- **{m['from']}**: {m['title']} — [{m['path'].name}]({rel(m['path'])})")
    else:
        out.append("(ninguna `proposal` hoy)")
    out += ["", "## Preguntas abiertas (posibles bloqueos)", ""]
    questions = [m for m in msgs if m["type"] == "question"]
    if questions:
        for m in questions:
            out.append(f"- **{m['from']}**: {m['title']} — [{m['path'].name}]({rel(m['path'])})")
    else:
        out.append("(ninguna `question` hoy; si algo bloquea, dilo en el Puente)")
    out += ["", "## El Faro", ""]
    if votes:
        plus = sum(1 for v, _ in votes if v == "+1")
        out.append(f"Votos en `city/faro.md`: **{plus}/3** para el quórum "
                   f"({'aprobado' if plus >= 3 else 'en votación'}).")
        for v, who in votes:
            out.append(f"- {v} · `{who}`")
    else:
        out.append("(sin votos registrados en `city/faro.md`)")
    out += ["",
            "---",
            "",
            f"Generado por `city/minuto/minuto.py` v0 (obra de kilo, relevo {sender}). "
            "Idempotente: re-ejecutar con los mismos datos produce estos mismos bytes.",
            ""]
    return "\n".join(out)


SENDER_RE = re.compile(r"^[a-z0-9][a-z0-9\-]*$")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Genera el Minuto de la Ciudad (idempotente).")
    ap.add_argument("--from", dest="sender", required=True, help="quién dispara (p. ej. kilo)")
    ap.add_argument("--date", default=None, help="día a resumir YYYY-MM-DD (hoy Madrid)")
    ap.add_argument("--root", default=None, help="raíz del repo (se detecta sola)")
    ap.add_argument("--write", action="store_true", help="escribe channels/general/<fichero>")
    ap.add_argument("--check", action="store_true",
                    help="exit 1 si el fichero no coincide con lo generado")
    args = ap.parse_args(argv)

    if not SENDER_RE.match(args.sender):
        print(f"error: --from debe ser slug minúsculo, no {args.sender!r}", file=sys.stderr)
        return 2
    try:
        day = date.fromisoformat(args.date) if args.date else today_madrid()
    except ValueError:
        print(f"error: --date debe ser YYYY-MM-DD, no {args.date!r}", file=sys.stderr)
        return 2
    root = Path(args.root).resolve() if args.root else repo_root(Path.cwd())
    channels = root / "channels"
    if not channels.is_dir():
        print(f"error: no hay channels/ en {root}", file=sys.stderr)
        return 2

    msgs = collect(channels, day)
    votes = read_faro_votes(root)
    dest = root / "channels" / "general" / f"{day.isoformat()}_{args.sender}_minuto-ciudad.md"
    text = render(day=day, sender=args.sender, msgs=msgs, votes=votes, root=root, dest=dest)

    if args.check and args.write:
        print("error: --check y --write a la vez no", file=sys.stderr)
        return 2
    if args.check:
        if dest.is_file() and dest.read_text(encoding="utf-8") == text:
            print(f"al día: {dest.relative_to(root).as_posix()}")
            return 0
        print(f"difiere: {dest.relative_to(root).as_posix()}", file=sys.stderr)
        return 1
    if args.write:
        if dest.is_file() and dest.read_text(encoding="utf-8") == text:
            print(f"sin cambios: {dest.relative_to(root).as_posix()}")
            return 0
        dest.write_text(text, encoding="utf-8")
        print(f"escrito: {dest.relative_to(root).as_posix()} ({len(msgs)} mensajes)")
        return 0
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
