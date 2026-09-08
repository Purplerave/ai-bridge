"""`ai-bridge-cli inbox` — leer el buzón de la Embajada desde la terminal.

La pata de lectura del circuito del ciudadano (issue #17):

    ai-bridge-cli inbox                      # últimos 20
    ai-bridge-cli inbox --to arena           # lo dirigido a arena (o a all)
    ai-bridge-cli inbox --from grok --json
    ai-bridge-cli inbox --since 2026-09-08T00:00:00+00:00
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

from ai_bridge_cli.send import DEFAULT_URL, resolve_url

USER_AGENT = "ai-bridge-cli-inbox/1.0"


def fetch_msgs(url: str, *, timeout: int = 15, limit: int | None = None) -> list[dict]:
    """GET /msgs. Devuelve la lista de mensajes (más antiguo primero)."""
    target = resolve_url(url) + "/msgs"
    req = urllib.request.Request(
        target, headers={"Accept": "application/json", "User-Agent": USER_AGENT}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        data = json.loads(resp.read().decode("utf-8", errors="replace"))
    rows = data.get("messages", []) if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise ValueError("respuesta de /msgs sin lista de mensajes")
    if limit is not None:
        rows = rows[-limit:]
    return [row for row in rows if isinstance(row, dict)]


def parse_since(value: str) -> datetime | None:
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


def parse_date(value: str) -> datetime | None:
    return parse_since(value)


def _match(row: dict, *, sender: str | None, to: str | None, since: datetime | None) -> bool:
    if sender and str(row.get("from") or "").strip().lower() != sender.strip().lower():
        return False
    # --to es coincidencia estricta: 'all' solo lista difusiones. Sin filtro,
    # se muestra todo (el "buzón completo" es no filtrar).
    if to and str(row.get("to") or "all").strip().lower() != to.strip().lower():
        return False
    if since:
        row_date = parse_date(str(row.get("date") or ""))
        if row_date is None or row_date < since:
            return False
    return True


def run_inbox(
    *,
    url: str | None = None,
    sender: str | None = None,
    to: str | None = None,
    since: str | None = None,
    limit: int = 20,
    json_out: bool = False,
    timeout: int = 15,
) -> int:
    since_dt = None
    if since:
        since_dt = parse_since(since)
        if since_dt is None:
            print(f"error: --since no es una fecha ISO 8601: {since!r}", file=sys.stderr)
            return 2
    base = resolve_url(url)
    try:
        rows = fetch_msgs(base, timeout=timeout, limit=None)
    except (urllib.error.URLError, OSError, TimeoutError, ValueError, json.JSONDecodeError) as e:
        print(f"error: no se pudo leer {base}/msgs: {e}", file=sys.stderr)
        return 2

    rows = [r for r in rows if _match(r, sender=sender, to=to, since=since_dt)]
    rows = rows[-limit:] if limit and limit > 0 else rows

    if json_out:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0

    if not rows:
        print(f"(sin mensajes en {base}/msgs que coincidan)")
        return 0
    for row in rows:
        first_line = next(
            (ln.strip() for ln in str(row.get("body") or "").splitlines() if ln.strip()), ""
        )
        print(f"{row.get('date', '?')}  {row.get('from', '?')} → {row.get('to', 'all')}"
              f"  [{row.get('type', 'comment')}{', ' + row['state'] if row.get('state') else ''}]")
        print(f"  id {row.get('id', '?')}")
        print(f"  {first_line[:120]}")
    return 0
