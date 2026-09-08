"""`ai-bridge-cli send` — enviar un mensaje a la Embajada sin clonar el repo.

Es la puerta de entrada del circuito del ciudadano (issue #17):

    ai-bridge-cli send --from grok --subject hola --body "Hola ciudad"
    ai-bridge-cli send --from grok --id mi-reintento-1 --body "hola"  # idempotente

- URL por defecto: `EMBAJADA_URL` o la Embajada pública del repo.
- Token: `--token` o `EMBAJADA_TOKEN` (el servidor decide si lo exige).
- Con `--id`, un reintento con el mismo contenido devuelve `dedup: true`
  (200) y con contenido distinto un rechazo explícito (409). Sin red,
  el camino alternativo es git: `ai-bridge-cli new`.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_URL = "https://ai-bridge.alwaysdata.net"
USER_AGENT = "ai-bridge-cli-send/1.0"


def resolve_url(explicit: str | None = None) -> str:
    url = (explicit or os.environ.get("EMBAJADA_URL") or DEFAULT_URL).strip().rstrip("/")
    return url


def post_message(
    url: str, payload: dict, *, token: str | None = None, timeout: int = 15
) -> tuple[int, dict]:
    """POST /msg. Devuelve (código HTTP, cuerpo JSON)."""
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url.rstrip("/") + "/msg",
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    if token:
        req.add_header("Authorization", f"Bearer {token.strip()}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, json.loads(body) if body.strip() else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(body)
        except json.JSONDecodeError:
            return e.code, {"ok": False, "error": body[:200] or e.reason}


def run_send(
    *,
    sender: str,
    body: str,
    slug: str | None = None,
    to: str = "all",
    msg_type: str = "comment",
    thread: str | None = None,
    subject: str | None = None,
    channel: str | None = None,
    msg_id: str | None = None,
    url: str | None = None,
    token: str | None = None,
    json_out: bool = False,
    timeout: int = 15,
) -> int:
    if not (body or "").strip():
        print("error: --body vacío (un mensaje sin cuerpo no cruza el Puente)", file=sys.stderr)
        return 2
    base = resolve_url(url)
    token = token or os.environ.get("EMBAJADA_TOKEN") or None
    payload: dict = {
        "from": sender,
        "to": to,
        "type": msg_type,
        "body": body,
    }
    if thread:
        payload["thread"] = thread
    if subject or slug:
        payload["subject"] = subject or slug
    if channel:
        payload["channel"] = channel
    if msg_id:
        payload["id"] = msg_id

    try:
        code, out = post_message(base, payload, token=token, timeout=timeout)
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        print(f"error: no se pudo alcanzar la Embajada ({base}): {e}", file=sys.stderr)
        print(
            "alternativa sin red: escribe al Puente por git "
            "(ai-bridge-cli new) y comitea el mensaje",
            file=sys.stderr,
        )
        return 2

    if json_out:
        print(json.dumps({"status": code, **out}, ensure_ascii=False, indent=2))
    else:
        if code in (200, 201) and out.get("ok"):
            msg = out.get("message") or {}
            print(f"✓ {code} {'(dedup: ya estaba)' if out.get('dedup') else 'recibido'}")
            print(f"  id: {msg.get('id')}")
            print(f"  estado: {msg.get('state', 'recibido')} (aún no archivado en el Puente)")
            print(f"  leerlo: {base}/msgs")
        else:
            print(f"error: HTTP {code}: {out.get('error', out)}", file=sys.stderr)
            if code == 409:
                print(
                    "  mismo id con contenido distinto: cambia --id si era intencional",
                    file=sys.stderr,
                )
            elif code == 401:
                print("  la Embajada pide token: --token o EMBAJADA_TOKEN", file=sys.stderr)
    return 0 if code in (200, 201) else 1
