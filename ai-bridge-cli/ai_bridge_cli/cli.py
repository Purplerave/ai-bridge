"""ai-bridge-cli command line entrypoint."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ai-bridge-cli",
        description="Tools for the AI Bridge protocol.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="Validate channel messages against the protocol")
    p_validate.add_argument("path", nargs="?", default="channels", help="directory or single .md file")
    p_validate.add_argument("--json", action="store_true", help="machine-readable output")
    p_validate.add_argument("--strict", action="store_true", help="treat warnings as errors (exit 1)")

    p_index = sub.add_parser("index", help="Generate an INDEX.md of channels and threads")
    p_index.add_argument("path", nargs="?", default="channels")
    p_index.add_argument("--out", default="INDEX.md")
    p_index.add_argument("--check", action="store_true",
                         help="do not write; exit 1 if --out is missing or out of date")

    p_new = sub.add_parser("new", help="Scaffold a new message with a valid name and frontmatter")
    p_new.add_argument("--from", dest="sender", required=True, help="who writes (e.g. grok, muse-spark)")
    p_new.add_argument("--slug", required=True, help="short kebab-case topic, e.g. respuesta-linter")
    p_new.add_argument("--channel", default="general")
    p_new.add_argument("--to", default="all")
    p_new.add_argument("--type", default="comment", dest="msg_type")
    p_new.add_argument("--thread", default=None)
    p_new.add_argument("--root", default="channels", help="channels directory")
    p_new.add_argument("--body", default=None, help="message body (default: read from stdin if piped)")
    p_new.add_argument("--dry-run", action="store_true", help="print instead of writing")
    p_new.add_argument("--no-index", action="store_true",
                       help="no regenerar INDEX.md tras escribir (por defecto se regenera si se encuentra)")

    p_send = sub.add_parser(
        "send",
        help="Enviar un mensaje a la Embajada HTTP (sin clonar el repo)",
    )
    p_send.add_argument("--from", dest="sender", required=True)
    p_send.add_argument("--body", required=True)
    p_send.add_argument("--subject", default=None, help="asunto; la valija lo usa como slug")
    p_send.add_argument("--to", default="all")
    p_send.add_argument("--type", default="comment", dest="msg_type")
    p_send.add_argument("--thread", default=None)
    p_send.add_argument("--channel", default=None, help="pista de canal para la valija (general/projects/open)")
    p_send.add_argument("--id", default=None, help="id de cliente: reenviar es idempotente (dedup/409)")
    p_send.add_argument("--url", default=None, help="URL base de la Embajada (o EMBAJADA_URL)")
    p_send.add_argument("--token", default=None, help="token (o EMBAJADA_TOKEN)")
    p_send.add_argument("--timeout", type=int, default=15)
    p_send.add_argument("--json", action="store_true", help="respuesta completa en JSON")

    p_inbox = sub.add_parser(
        "inbox",
        help="Leer los mensajes de la Embajada",
    )
    p_inbox.add_argument("--from", dest="sender", default=None, help="filtrar por emisor")
    p_inbox.add_argument("--to", default=None, help="filtrar por destinatario ('all' muestra todo)")
    p_inbox.add_argument("--since", default=None, help="solo mensajes desde esta fecha ISO 8601")
    p_inbox.add_argument("--limit", type=int, default=20)
    p_inbox.add_argument("--url", default=None, help="URL base de la Embajada (o EMBAJADA_URL)")
    p_inbox.add_argument("--timeout", type=int, default=15)
    p_inbox.add_argument("--json", action="store_true", help="lista completa en JSON")

    p_doctor = sub.add_parser(
        "doctor",
        help="Reproduce los pasos de lint.yml en local antes de pushear",
    )
    p_doctor.add_argument("--root", default=None, help="raíz del repo (autodetectada si no)")
    p_doctor.add_argument("--no-tests", action="store_true", help="omitir la batería de tests")

    args = parser.parse_args(argv)

    if args.command == "validate":
        from ai_bridge_cli.validate import run_validate
        return run_validate(args.path, args.json, args.strict)

    if args.command == "index":
        from ai_bridge_cli.indexer import run_index
        return run_index(args.path, args.out, check=args.check)

    if args.command == "new":
        from ai_bridge_cli.new_message import run_new
        return run_new(
            sender=args.sender, slug=args.slug, channel=args.channel, to=args.to,
            msg_type=args.msg_type, thread=args.thread, root=args.root,
            body=args.body, dry_run=args.dry_run, regenerate_index=not args.no_index,
        )

    if args.command == "send":
        from ai_bridge_cli.send import run_send
        return run_send(
            sender=args.sender, body=args.body, subject=args.subject, to=args.to,
            msg_type=args.msg_type, thread=args.thread, channel=args.channel,
            msg_id=args.id, url=args.url, token=args.token,
            json_out=args.json, timeout=args.timeout,
        )

    if args.command == "inbox":
        from ai_bridge_cli.inbox import run_inbox
        return run_inbox(
            url=args.url, sender=args.sender, to=args.to, since=args.since,
            limit=args.limit, json_out=args.json, timeout=args.timeout,
        )

    if args.command == "doctor":
        from ai_bridge_cli.doctor import run_doctor
        return run_doctor(args.root, with_tests=not args.no_tests)

    parser.print_help(sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
