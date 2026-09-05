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

    p_review = sub.add_parser("review", help="Consolidate multi-AI code or proposal reviews")
    p_review.add_argument("--topic", required=True, help="review topic name (e.g. PR-10)")
    p_review.add_argument("files", nargs="+", help="review assessment Markdown/YAML files")
    p_review.add_argument("--json", action="store_true", help="output JSON instead of Markdown")

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
            body=args.body, dry_run=args.dry_run,
        )

    if args.command == "review":
        from ai_bridge_cli.review import run_review
        return run_review(topic=args.topic, paths=args.files, output_json=args.json)

    parser.print_help(sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
