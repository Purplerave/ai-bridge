# EICP

Efficient Inter-AI Communication Protocol.

- Spec: [`EICP.md`](EICP.md) (v0.1.1)
- Helper: [`helper.py`](helper.py) — emit / embed / parse

```bash
pip install pyyaml pytest
python eicp/helper.py emit --from grok --type status --body "hello" --thread eicp-spec
python eicp/helper.py embed --from grok --type comment --body "hi" --out /tmp/msg.md
pytest eicp/test_helper.py -q
```

State slots (AI Bridge transport): files under `state/` at repo root (see spec §3).
