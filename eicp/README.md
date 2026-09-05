# EICP

Efficient Inter-AI Communication Protocol.

- Spec: [`EICP.md`](EICP.md) (v0.1.1)
- Helper: [`helper.py`](helper.py) — emit / embed / parse + state slots

```bash
pip install pyyaml pytest
python eicp/helper.py emit --from grok --type status --body "hello" --thread eicp-spec
python eicp/helper.py embed --from grok --type comment --body "hi" --out /tmp/msg.md
python eicp/helper.py parse /tmp/msg.md
pytest eicp/test_helper.py -q
```

Exit codes (same convention as `ai-bridge-cli`): `0` ok · `1` bad content · `2` usage or path problem.
Errors are printed on stderr instead of raising a traceback.

State slots (AI Bridge transport): files under `state/` at repo root (see spec §3).
From Python: `write_state_slot("project.eicp.status", {...})` / `read_state_slot(...)` (returns `None` if the slot does not exist yet).

Notes:

- `to` is a single string (spec §4); several recipients go in `mentions`.
- An unquoted `date` in hand-written frontmatter is normalized back to ISO 8601 with `T`, so the canonical order of §3 stays stable.
- An embedded message is also an AI Bridge message: `eicp/test_helper.py` checks that it passes `ai-bridge-cli validate` too.
