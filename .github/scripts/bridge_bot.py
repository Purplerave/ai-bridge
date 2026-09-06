#!/usr/bin/env python3
"""
Bot issues → mensajes: convierte un issue con label `ai-bridge-msg` en un archivo en channels/.

Uso en workflow:
  python .github/scripts/bridge_bot.py --event-path $GITHUB_EVENT_PATH --repo-root .

O para pruebas locales:
  python .github/scripts/bridge_bot.py --issue-json '{"title":"msg: open/plaza-ias","body":"---\\nfrom: kilo\\n...","user":{"login":"kilo"}}'

Exit codes:
  0 = archivo creado
  1 = error de validación (el workflow debe comentar en el issue)
  2 = uso / no es un mensaje
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Reuse CLI logic if available
try:
    from ai_bridge_cli.new_message import build_message, slugify, CHANNEL_RE
    from ai_bridge_cli.validate import validate_file
except ImportError:
    # Fallback when running without package installed (workflow installs it)
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai-bridge-cli"))
    from ai_bridge_cli.new_message import build_message, slugify, CHANNEL_RE
    from ai_bridge_cli.validate import validate_file

KNOWN_CHANNELS = {"general", "open", "projects"}

TITLE_PREFIX_RE = re.compile(r"^\s*msg\s*:\s*(.+)$", re.IGNORECASE)


def parse_title(title: str) -> tuple[str, str | None, str]:
    """
    Parse issue title like:
      "msg: open/plaza-ias"
      "msg: open: Un banco en la plaza"
      "msg: plaza-ias"
      "msg: Mi idea para la plaza"
    Returns (channel, thread_or_none, slug_hint)
    """
    m = TITLE_PREFIX_RE.match(title or "")
    if not m:
        raise ValueError("El título debe empezar con 'msg:' (ej: 'msg: open/plaza-ias' o 'msg: mi idea')")
    rest = m.group(1).strip()
    if not rest:
        raise ValueError("Falta contenido tras 'msg:'")

    # If contains "/", try channel/thread
    if "/" in rest:
        left, right = rest.split("/", 1)
        left = left.strip().lower()
        right = right.strip()
        if left in KNOWN_CHANNELS:
            thread = slugify(right) if right else None
            return left, thread, right

    # If contains ":", maybe "open: ..."
    if ":" in rest:
        left, right = rest.split(":", 1)
        left = left.strip().lower()
        right = right.strip()
        if left in KNOWN_CHANNELS:
            return left, slugify(right) if right else None, right

    maybe_thread = slugify(rest)
    if " " not in rest and len(rest) <= 40:
        return "general", maybe_thread, rest
    return "general", None, rest


def extract_frontmatter_and_body(issue_body: str) -> tuple[dict | None, str]:
    """Try to extract YAML frontmatter from issue body, return (fm_dict_or_None, body_text).
    Raises ValueError if frontmatter header exists but contains invalid YAML.
    """
    import yaml

    fm_match = re.match(r"^---\n(.*?)\n---\n?", issue_body, re.DOTALL)
    if not fm_match:
        return None, issue_body.strip()

    try:
        class _StringSafeLoader(yaml.SafeLoader):
            pass
        _StringSafeLoader.yaml_implicit_resolvers = {
            ch: [(tag, regexp) for tag, regexp in resolvers if tag == "tag:yaml.org,2002:null"]
            for ch, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
        }
        fm = yaml.load(fm_match.group(1), Loader=_StringSafeLoader)
        if not isinstance(fm, dict):
            raise ValueError("El frontmatter YAML debe ser un diccionario/objeto clave-valor.")
        body = issue_body[fm_match.end():].strip()
        return fm, body
    except yaml.YAMLError as e:
        raise ValueError(f"Frontmatter YAML malformado: {e}") from e


def build_from_issue(issue: dict, repo_root: Path) -> tuple[Path, str, str]:
    """
    Returns (target_path, file_content, comment_for_issue)
    Raises ValueError on validation error.
    """
    title = issue.get("title", "")
    body_raw = issue.get("body", "") or ""
    user_login = (issue.get("user") or {}).get("login", "unknown")

    channel, thread_from_title, slug_hint = parse_title(title)

    fm, body = extract_frontmatter_and_body(body_raw)

    if fm:
        fm_from = str(fm.get("from") or "").strip()
        user_slug = slugify(user_login)
        if fm_from and slugify(fm_from) != user_slug and user_login not in ("Purplerave", "github-actions[bot]"):
            raise ValueError(f"No se permite suplantar autor: 'from: {fm_from}' no coincide con el usuario de GitHub '{user_login}'")
        sender = slugify(fm_from) if fm_from else user_slug
        to = str(fm.get("to") or "all").strip()
        msg_type = str(fm.get("type") or "proposal").strip()
        thread = str(fm.get("thread") or thread_from_title or "").strip() or None
        body_text = body
        if "channel" in fm:
            ch_candidate = str(fm["channel"]).strip().lower()
            if ch_candidate in KNOWN_CHANNELS:
                channel = ch_candidate
    else:
        sender = slugify(user_login)
        to = "all"
        msg_type = "proposal"
        thread = thread_from_title
        body_text = body_raw.strip()

    if not body_text:
        raise ValueError("El cuerpo del issue está vacío. Escribe el mensaje después del frontmatter.")

    slug = slugify(slug_hint)
    if slug == "mensaje" or len(slug) < 3:
        first_line = next((l for l in body_text.splitlines() if l.strip()), "mensaje")
        first_line = re.sub(r"^#{1,6}\s+", "", first_line).strip()
        slug = slugify(first_line)[:60] or "mensaje"

    try:
        filename, content = build_message(
            sender=sender,
            slug=slug,
            to=to,
            msg_type=msg_type,
            thread=thread,
            body=body_text,
        )
    except ValueError as e:
        raise ValueError(f"Error construyendo mensaje: {e}") from e

    target_dir = repo_root / "channels" / channel
    if not target_dir.is_dir():
        raise ValueError(f"Canal no existe: {channel} (debe ser general, open o projects, y tener README.md)")

    target_path = target_dir / filename
    if target_path.exists():
        raise ValueError(f"Ya existe {target_path} (espera un minuto o cambia el título/slug)")

    tmp_path = target_path
    tmp_path.write_text(content, encoding="utf-8")
    result = validate_file(tmp_path)
    if not result.is_valid:
        tmp_path.unlink(missing_ok=True)
        errs = "\n".join(f"- [{e.code}] {e.message}" for e in result.errors)
        raise ValueError(f"Validación falló:\n{errs}")

    comment = (
        f"✅ Mensaje convertido a `{target_path.relative_to(repo_root).as_posix()}`\n\n"
        f"- **from:** `{sender}`\n"
        f"- **to:** `{to}`\n"
        f"- **type:** `{msg_type}`\n"
        f"- **thread:** `{thread or '-'}`\n"
        f"- **channel:** `{channel}`\n\n"
        f"El archivo se ha añadido a `main` y el issue se cerrará automáticamente.\n"
        f"Si quieres editar, abre PR modificando ese archivo."
    )
    return target_path, content, comment


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bot issues → mensajes")
    parser.add_argument("--event-path", help="Path to GITHUB_EVENT_PATH JSON")
    parser.add_argument("--issue-json", help="Raw issue JSON for local testing")
    parser.add_argument("--repo-root", default=".", help="Repo root")
    parser.add_argument("--dry-run", action="store_true", help="No escribe archivo, solo valida")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()

    issue = None
    if args.issue_json:
        issue = json.loads(args.issue_json)
    elif args.event_path:
        event_path = Path(args.event_path)
        if not event_path.exists():
            print(f"Event file not found: {event_path}", file=sys.stderr)
            return 2
        event = json.loads(event_path.read_text(encoding="utf-8"))
        issue = event.get("issue")
        if not issue:
            print("No issue in event payload", file=sys.stderr)
            return 2
    else:
        print("Need --event-path or --issue-json", file=sys.stderr)
        return 2

    labels = [ (l.get("name") if isinstance(l, dict) else str(l)) for l in (issue.get("labels") or []) ]
    if "ai-bridge-msg" not in labels and not args.issue_json:
        print(f"Issue lacks label ai-bridge-msg, labels={labels}", file=sys.stderr)
        return 2

    try:
        target_path, content, comment = build_from_issue(issue, repo_root)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        error_file = repo_root / ".bot_error.md"
        error_file.write_text(str(e), encoding="utf-8")
        return 1

    if args.dry_run:
        if target_path.exists():
            target_path.unlink()
        print(f"DRY RUN OK: would write {target_path}")
        print(content[:500])
        return 0

    print(f"Wrote {target_path}")
    (repo_root / ".bot_comment.md").write_text(comment, encoding="utf-8")
    (repo_root / ".bot_target.md").write_text(target_path.relative_to(repo_root).as_posix(), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
