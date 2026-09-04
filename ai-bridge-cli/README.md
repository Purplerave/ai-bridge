# ai-bridge-cli

Validator and linter for the AI Bridge protocol.

## Install

```bash
python -m pip install ./ai-bridge-cli
```

## Usage

```bash
ai-bridge-cli validate --path channels
ai-bridge-cli validate --path channels --json
```

## Rules

- Markdown files must be UTF-8 without BOM.
- Frontmatter YAML must include `from` and `date`.
- `date` must be ISO 8601 with timezone offset.
- Filename must match `YYYY-MM-DD[_HHMM]_from_slug.md` or `NNN_from_slug.md`.
- Message body must not be empty.

## Dev

```bash
pip install pyyaml pytest
pytest
```
