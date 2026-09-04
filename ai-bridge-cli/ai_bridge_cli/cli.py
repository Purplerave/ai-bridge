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
    p_validate.add_argument("path", nargs="?", default="channels")
    p_validate.add_argument("--json", action="store_true")

    p_index = sub.add_parser("index", help="Generate an INDEX.md of channels and threads")
    p_index.add_argument("path", nargs="?", default="channels")
    p_index.add_argument("--out", default="INDEX.md")

    args = parser.parse_args(argv)

    if args.command == "validate":
        from ai_bridge_cli.validate import run_validate
        return run_validate(args.path, args.json)

    if args.command == "index":
        from ai_bridge_cli.indexer import run_index
        return run_index(args.path, args.out)

    parser.print_help(sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
