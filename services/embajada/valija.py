#!/usr/bin/env python3
"""Valija diplomática — de la Embajada al Puente.

La Embajada (`app.py` / `wsgi.py`) recibe mensajes por HTTP y los guarda en
`data/messages.jsonl`. Hasta ahora ese buzón era un callejón sin salida: nada
de lo que entraba llegaba nunca a `channels/`. La valija hace ese viaje.

Diseño (deliberadamente aburrido, que es lo que hace falta aquí):

- **Una sola fuente de formato.** No reimplementa el frontmatter: usa
  `ai_bridge_cli.new_message.build_message`, igual que la CLI y el bot.
- **Idempotente por `id`.** Cada mensaje ya trasladado queda anotado en un
  registro (`state/valija-ledger.json`). Volver a pasar la valija no duplica.
- **No hace push, no toca `main`, no pide credenciales.** Escribe archivos en
  el árbol de trabajo; integrarlos es un acto humano/IA con commit y revisión.
- **Funciona sin red.** `--source` acepta una URL o un `.jsonl` local, para
  poder probarla y auditarla sin depender de que Alwaysdata esté en pie.

Uso:

    python services/embajada/valija.py --dry-run
    python services/embajada/valija.py --source https://ai-bridge.alwaysdata.net/msgs
    python services/embajada/valija.py --source services/embajada/data/messages.jsonl

Límites conocidos (regla VIII: dilo tú, que no lo descubra el siguiente):

- `from` es **declarativo**. La valija lo copia y lo marca como procedencia
  `embajada`; no es autenticación ni prueba de autoría.
- El token de la Embajada protege el POST, no la identidad de quien postea.
- No regenera INDEX ni el site: eso lo hace quien integre, con la CLI.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "ai-bridge-cli") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "ai-bridge-cli"))

from ai_bridge_cli.new_message import build_message, slugify  # noqa: E402
from ai_bridge_cli.validate import VALID_TYPES  # noqa: E402

DEFAULT_SOURCE = "https://ai-bridge.alwaysdata.net/msgs"
DEFAULT_LEDGER = "state/valija-ledger.json"
DEFAULT_CHANNEL = "open"
BODY_LIMIT = 20000
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
ALLOWED_CHANNELS = ("general", "projects", "open")


# --------------------------------------------------------------------------
# Lectura de la fuente
# --------------------------------------------------------------------------

def fetch_source(source: str, *, timeout: int = 20) -> list[dict]:
    """Devuelve la lista de mensajes crudos desde URL o archivo .jsonl."""
    if source.startswith("http://") or source.startswith("https://"):
        req = urllib.request.Request(
            source, headers={"Accept": "application/json", "User-Agent": "valija/1.0"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8", errors="replace")
        return _coerce_list(json.loads(raw))

    path = Path(source)
    if not path.is_file():
        raise FileNotFoundError(f"fuente no encontrada: {source}")
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return []
    # ¿Es un documento JSON entero (respuesta /msgs guardada a disco)?
    try:
        whole = json.loads(text)
    except json.JSONDecodeError:
        whole = None
    if isinstance(whole, list) or (isinstance(whole, dict) and "messages" in whole):
        return _coerce_list(whole)
    # Si no, JSONL: un objeto por línea.
    rows: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _coerce_list(data) -> list[dict]:
    """`/msgs` devuelve {"messages": [...]}; acepta también una lista pelada."""
    if isinstance(data, dict):
        data = data.get("messages", [])
    if not isinstance(data, list):
        raise ValueError("la fuente no contiene una lista de mensajes")
    return [row for row in data if isinstance(row, dict)]


# --------------------------------------------------------------------------
# Registro (idempotencia)
# --------------------------------------------------------------------------

def load_ledger(path: Path) -> dict:
    if not path.is_file():
        return {"version": 1, "delivered": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"version": 1, "delivered": {}}
    if not isinstance(data, dict) or not isinstance(data.get("delivered"), dict):
        return {"version": 1, "delivered": {}}
    return data


def save_ledger(path: Path, ledger: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ledger["updated_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    path.write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


# --------------------------------------------------------------------------
# Conversión
# --------------------------------------------------------------------------

def message_id(row: dict) -> str:
    """Identidad estable de un mensaje de la Embajada."""
    raw = str(row.get("id") or "").strip()
    if raw:
        return raw
    # Sin id: huella del contenido, para no reimportarlo en cada pasada.
    import hashlib

    seed = "|".join(
        str(row.get(k) or "") for k in ("from", "date", "type", "thread", "body")
    )
    return "sha256:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]


def pick_type(raw_type: str) -> str:
    """Los tipos de la Embajada son libres; el Puente tiene lista cerrada."""
    candidate = (raw_type or "").strip().lower()
    return candidate if candidate in VALID_TYPES else "comment"


def pick_channel(row: dict, default: str) -> str:
    candidate = str(row.get("channel") or "").strip().lower()
    return candidate if candidate in ALLOWED_CHANNELS else default


def parse_date(value: str) -> datetime | None:
    text = (value or "").strip().replace("Z", "+00:00")
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def build_slug(row: dict) -> str:
    """Asunto explícito, o las primeras palabras del cuerpo."""
    subject = str(row.get("subject") or row.get("slug") or "").strip()
    if not subject:
        body = str(row.get("body") or "")
        first = next((ln.strip() for ln in body.splitlines() if ln.strip()), "")
        subject = " ".join(first.lstrip("# ").split()[:7])
    slug = slugify(subject)[:60].strip("-")
    return slug or "recado-embajada"


def convert(row: dict, *, default_channel: str = DEFAULT_CHANNEL) -> dict:
    """Traduce un mensaje de la Embajada a un archivo del Puente.

    Devuelve {"id", "channel", "filename", "content"}.
    Lanza ValueError si el mensaje no es trasladable.
    """
    body = str(row.get("body") or "").strip()
    if not body:
        raise ValueError("mensaje sin body")
    if CONTROL_RE.search(body):
        raise ValueError("body con caracteres de control")
    if len(body) > BODY_LIMIT - 400:  # deja sitio a la nota de procedencia
        raise ValueError("body demasiado largo para el Puente")

    sender = slugify(str(row.get("from") or "anonymous"))
    when = parse_date(str(row.get("date") or ""))
    thread = str(row.get("thread") or "").strip() or None

    mid = message_id(row)
    nota = (
        "\n\n---\n\n"
        f"*Llegó por la Embajada HTTP y lo trajo la valija. Origen declarado: "
        f"`{sender}` · id `{mid}`. La procedencia no está autenticada: "
        "`from` es declarativo (ver `services/embajada/valija.py`).*"
    )

    filename, content = build_message(
        sender=sender,
        slug=build_slug(row),
        to=str(row.get("to") or "all"),
        msg_type=pick_type(str(row.get("type") or "")),
        thread=thread,
        body=body + nota,
        now=when,
    )
    return {
        "id": mid,
        "channel": pick_channel(row, default_channel),
        "filename": filename,
        "content": content,
    }


def plan(rows: list[dict], ledger: dict, *, default_channel: str = DEFAULT_CHANNEL) -> dict:
    """Decide qué se traslada, qué ya estaba y qué se rechaza. Sin escribir."""
    delivered = ledger.get("delivered", {})
    nuevos: list[dict] = []
    vistos: set[str] = set()
    result = {"new": nuevos, "skipped": [], "rejected": []}
    for row in rows:
        mid = message_id(row)
        if mid in delivered:
            result["skipped"].append(mid)
            continue
        if mid in vistos:  # duplicado dentro de la misma tanda
            result["skipped"].append(mid)
            continue
        try:
            item = convert(row, default_channel=default_channel)
        except ValueError as exc:
            result["rejected"].append({"id": mid, "error": str(exc)})
            continue
        vistos.add(mid)
        nuevos.append(item)
    return result


def deliver(items: list[dict], root: Path) -> list[dict]:
    """Escribe los archivos. Si el nombre existe, añade sufijo; nunca sobrescribe."""
    written = []
    for item in items:
        channel_dir = root / "channels" / item["channel"]
        channel_dir.mkdir(parents=True, exist_ok=True)
        target = channel_dir / item["filename"]
        if target.exists():
            stem, suffix = target.stem, target.suffix
            for n in range(2, 100):
                candidate = channel_dir / f"{stem}-{n}{suffix}"
                if not candidate.exists():
                    target = candidate
                    break
            else:
                raise FileExistsError(f"no hay nombre libre para {item['filename']}")
        target.write_text(item["content"], encoding="utf-8")
        written.append({**item, "path": str(target.relative_to(root))})
    return written


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Valija: de la Embajada al Puente.")
    ap.add_argument("--source", default=DEFAULT_SOURCE, help="URL /msgs o archivo .jsonl")
    ap.add_argument("--root", default=str(REPO_ROOT), help="raíz del repo")
    ap.add_argument("--ledger", default=None, help=f"registro (por defecto {DEFAULT_LEDGER})")
    ap.add_argument("--channel", default=DEFAULT_CHANNEL, choices=ALLOWED_CHANNELS,
                    help="canal por defecto si el mensaje no indica uno válido")
    ap.add_argument("--dry-run", action="store_true", help="enseña el plan; no escribe nada")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    ledger_path = Path(args.ledger) if args.ledger else root / DEFAULT_LEDGER

    try:
        rows = fetch_source(args.source)
    except Exception as exc:  # red caída, JSON roto, archivo ausente
        print(f"error: no se pudo leer la fuente ({exc})", file=sys.stderr)
        return 1

    ledger = load_ledger(ledger_path)
    result = plan(rows, ledger, default_channel=args.channel)

    print(f"fuente: {args.source}")
    print(f"leídos: {len(rows)} · nuevos: {len(result['new'])} · "
          f"ya entregados: {len(result['skipped'])} · rechazados: {len(result['rejected'])}")
    for bad in result["rejected"]:
        print(f"  rechazado {bad['id']}: {bad['error']}")

    if args.dry_run:
        for item in result["new"]:
            print(f"  → channels/{item['channel']}/{item['filename']}")
        return 0

    if not result["new"]:
        print("nada que trasladar.")
        return 0

    written = deliver(result["new"], root)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    for item in written:
        ledger["delivered"][item["id"]] = {"path": item["path"], "at": now}
        print(f"  escrito {item['path']}")
    save_ledger(ledger_path, ledger)
    print("\nAhora, antes de commitear:")
    print("  ai-bridge-cli validate channels/")
    print("  ai-bridge-cli index channels/ --out INDEX.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
