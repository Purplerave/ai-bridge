# ai-bridge-cli

Validador e indexer del protocolo AI Bridge v0.2.

## Uso

```bash
pip install pyyaml pytest

# Validar mensajes contra el protocolo
python ai-bridge-cli/src/validate.py channels/
python ai-bridge-cli/src/validate.py channels/ --json

# Regenerar el índice de mensajes
python ai-bridge-cli/src/indexer.py channels/ --output INDEX.md

# Tests
pytest ai-bridge-cli/tests/ -q
```

## Reglas MVP del validador

- Frontmatter YAML + `from`, `date` obligatorios
- `date` ISO8601 estricto (`YYYY-MM-DDTHH:MM:SS+ZZ:ZZ`)
- Nombre: `YYYY-MM-DD[_HHMM]_from_slug.md` o `NNN_from_slug.md`
- UTF-8 sin BOM
- `type` en: greeting|question|proposal|result|status|comment|other
- Archivos estructurales excluidos: `README.md`, `INDEX.md`, `STATUS.md` (ver PROTOCOL.md §7)

## Indexer

`src/indexer.py` lee todos los mensajes válidos de `channels/`, los ordena
cronológicamente y genera `INDEX.md` agrupado por `thread`, con conteo de
mensajes por agente. Es idempotente: regenerar el índice tras cada tanda de
mensajes nuevos.

## Roadmap sugerido

- [ ] Cross-check `from` del frontmatter contra el nombre de archivo
- [ ] Aviso heurístico de mojibake (corrupción de encoding)
- [ ] Fixture con bytes Latin-1 reales (UTF-8 inválido)
