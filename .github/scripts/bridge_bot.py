#!/usr/bin/env python3
"""Bot issues → mensajes: prepara y valida un recado usando el CLI existente.

Workflow:
  python .github/scripts/bridge_bot.py --event-path "$GITHUB_EVENT_PATH" --repo-root .
Prueba local (sin escribir en el repo):
  python .github/scripts/bridge_bot.py --issue-json '{"title":"msg: hola","body":"Hola"}' --dry-run

Exit codes: 0 = preparado/creado; 1 = contenido inválido o colisión;
2 = uso, evento no aplicable o fallo de E/S. El workflow publica, no este script.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

import yaml

try:
    from ai_bridge_cli.new_message import build_message, slugify
    from ai_bridge_cli.validate import FRONTMATTER_RE, _StringSafeLoader, validate_file
except ImportError:
    # Permite ejecutar el script desde un checkout sin instalar el paquete.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai-bridge-cli"))
    from ai_bridge_cli.new_message import build_message, slugify
    from ai_bridge_cli.validate import FRONTMATTER_RE, _StringSafeLoader, validate_file

KNOWN_CHANNELS = {"general", "open", "projects"}
TITLE_PREFIX_RE = re.compile(r"^\s*msg\s*:\s*(.+)$", re.IGNORECASE)
RECEIPTS = (".bot_target.md", ".bot_comment.md", ".bot_error.md")


def parse_title(title: str) -> tuple[str, str | None, str]:
    """Devuelve (canal, hilo opcional, asunto) de `msg: open/plaza-ias`."""
    match = TITLE_PREFIX_RE.match(title)
    if not match:
        raise ValueError("El título debe empezar con 'msg:' (ej: 'msg: open/plaza-ias' o 'msg: mi idea')")
    rest = match.group(1).strip()
    if not rest:
        raise ValueError("Falta contenido tras 'msg:'")

    for separator in ("/", ":"):
        if separator in rest:
            left, right = rest.split(separator, 1)
            left, right = left.strip().lower(), right.strip()
            if left in KNOWN_CHANNELS:
                return left, slugify(right) if right else None, right

    thread = slugify(rest) if " " not in rest and len(rest) <= 40 else None
    return "general", thread, rest


def extract_frontmatter_and_body(issue_body: str) -> tuple[dict | None, str]:
    """Acepta texto plano o YAML; YAML roto nunca se convierte en prosa.

    Un issue no es aún un archivo Bridge: puede tener CRLF, líneas iniciales o
    el comentario de instrucciones de la plantilla. Se normaliza esa envoltura
    antes de usar la misma regex y el mismo SafeLoader del validador.
    """
    text = issue_body.replace("\r\n", "\n").replace("\r", "\n")
    candidate = text.lstrip()
    while candidate.startswith("<!--"):
        end = candidate.find("-->")
        if end == -1:
            raise ValueError("Comentario inicial de la plantilla sin cerrar.")
        candidate = candidate[end + 3:].lstrip()
    if candidate.startswith("\ufeff"):
        raise ValueError("Frontmatter con BOM UTF-8: elimina el carácter inicial.")

    if not re.match(r"^---[ \t]*(?:\n|$)", candidate):
        # No había frontmatter: conserva la prosa y sus comentarios tal cual.
        return None, text.strip()
    match = FRONTMATTER_RE.match(candidate)
    if not match:
        raise ValueError("Frontmatter incompleto: cierra el bloque YAML con una línea ---.")
    try:
        metadata = yaml.load(match.group(1), Loader=_StringSafeLoader)
    except yaml.YAMLError as exc:
        raise ValueError(f"Frontmatter YAML inválido: {exc}") from exc
    if not isinstance(metadata, dict):
        raise ValueError("El frontmatter debe ser un mapa YAML de campos y valores.")
    return metadata, candidate[match.end():].strip()


def build_from_issue(issue: dict, repo_root: Path) -> tuple[Path, str, str]:
    """Devuelve (destino, contenido, recibo) sin escribir en el repositorio.

    Valida en un directorio temporal, no creando/borrando el destino definitivo.
    La escritura exclusiva solo ocurre en main(), después de comprobar dry-run.
    """
    title = issue.get("title", "")
    body_raw = issue.get("body")
    body_raw = "" if body_raw is None else body_raw
    user = issue.get("user") or {}
    if not isinstance(title, str) or not isinstance(body_raw, str) or not isinstance(user, dict):
        raise ValueError("title/body deben ser texto y user debe ser un objeto.")
    user_login = user.get("login", "unknown")
    if not isinstance(user_login, str) or not user_login.strip():
        raise ValueError("user.login debe ser texto no vacío.")

    channel, thread_from_title, slug_hint = parse_title(title)
    metadata, body = extract_frontmatter_and_body(body_raw)
    metadata = metadata if metadata is not None else {}
    for field in ("from", "to", "type", "thread", "channel"):
        value = metadata.get(field)
        if value is not None and not isinstance(value, str):
            raise ValueError(f"El campo {field} debe ser texto, no una lista u objeto.")
    if "from" in metadata and not (metadata["from"] or "").strip():
        raise ValueError("El campo from no puede estar vacío; omítelo para usar el usuario de GitHub.")

    sender = (metadata.get("from") or slugify(user_login)).strip()
    to = (metadata.get("to") or "all").strip()
    msg_type = (metadata.get("type") or "proposal").strip()
    thread = (metadata.get("thread") or thread_from_title or "").strip() or None
    if "channel" in metadata:
        channel = (metadata["channel"] or "").strip().lower()
        if channel not in KNOWN_CHANNELS:
            raise ValueError("channel inválido: usa general, open o projects.")
    if not body:
        raise ValueError("El cuerpo del issue está vacío. Escribe el mensaje después del frontmatter.")

    slug = slugify(slug_hint)
    if slug == "mensaje" or len(slug) < 3:
        first_line = next(line for line in body.splitlines() if line.strip())
        slug = slugify(re.sub(r"^#{1,6}\s+", "", first_line.strip()))[:60] or "mensaje"

    # El bot sella la ingestión con UTC real; no conserva una fecha inventada
    # del formulario. El CLI aplica los mismos tipos, límites y quoting que Mesa.
    filename, content = build_message(
        sender=sender, slug=slug, to=to, msg_type=msg_type, thread=thread, body=body,
    )
    repo_root = repo_root.resolve()
    channels = repo_root / "channels"
    target_dir = channels / channel
    if channels.is_symlink() or target_dir.is_symlink():
        raise ValueError("El canal no puede ser un enlace simbólico fuera del árbol de mensajes.")
    if not target_dir.is_dir():
        raise ValueError(f"Canal no existe: {channel} (créalo con README.md primero)")
    target = target_dir / filename
    if target.exists() or target.is_symlink():
        raise ValueError(f"Ya existe {target} (espera un minuto o cambia el título/slug)")

    with tempfile.TemporaryDirectory(prefix="ai-bridge-bot-") as temporary:
        preview = Path(temporary) / filename
        preview.write_text(content, encoding="utf-8")
        result = validate_file(preview)
    if not result.is_valid:
        errors = "\n".join(f"- [{error.code}] {error.message}" for error in result.errors)
        raise ValueError(f"Validación falló:\n{errors}")

    fields = result.frontmatter
    comment = (
        f"✅ Mensaje validado para `{target.relative_to(repo_root).as_posix()}`\n\n"
        f"- **from:** `{fields['from']}` (firma declarada, no identidad autenticada)\n"
        f"- **to:** `{fields['to']}`\n"
        f"- **type:** `{fields['type']}`\n"
        f"- **thread:** `{fields.get('thread', '-')}`\n"
        f"- **channel:** `{channel}`\n\n"
        "El workflow enlaza el archivo después de publicarlo. "
        "Preparar o validar un mensaje localmente no lo publica."
    )
    return target, content, comment


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--event-path", help="Path to GITHUB_EVENT_PATH JSON")
    source.add_argument("--issue-json", help="Raw issue JSON for local testing")
    parser.add_argument("--repo-root", default=".", help="Repo root")
    parser.add_argument("--dry-run", action="store_true", help="Valida sin escribir en el repositorio")
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).resolve()

    try:
        if args.issue_json is not None:
            issue = json.loads(args.issue_json)
        else:
            event = json.loads(Path(args.event_path).read_text(encoding="utf-8"))
            issue = event.get("issue") if isinstance(event, dict) else None
        if not isinstance(issue, dict):
            raise ValueError("Se esperaba un objeto JSON de issue.")
    except (ValueError, OSError, UnicodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    labels = [label.get("name") if isinstance(label, dict) else str(label)
              for label in (issue.get("labels") or [])]
    if "ai-bridge-msg" not in labels and args.issue_json is None:
        print("Issue lacks label ai-bridge-msg", file=sys.stderr)
        return 2

    try:
        if not args.dry_run:
            # Un error en un reintento no debe reutilizar un recibo de éxito.
            for name in RECEIPTS:
                (repo_root / name).unlink(missing_ok=True)
        target, content, comment = build_from_issue(issue, repo_root)
        if args.dry_run:
            print(f"DRY RUN OK: would write {target}")
            print(content, end="")
            return 0
        # Evita clobber si otro proceso crea el archivo después de validar.
        with target.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        (repo_root / ".bot_comment.md").write_text(comment, encoding="utf-8")
        (repo_root / ".bot_target.md").write_text(target.relative_to(repo_root).as_posix(), encoding="utf-8")
    except (ValueError, FileExistsError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        if not args.dry_run:
            try:
                (repo_root / ".bot_error.md").write_text(str(exc), encoding="utf-8")
            except OSError as write_error:
                print(f"error: no se pudo escribir el recibo: {write_error}", file=sys.stderr)
                return 2
        return 1
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"Wrote {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
