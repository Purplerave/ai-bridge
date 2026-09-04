# ai-bridge-cli

Validador e indexador del protocolo AI Bridge v0.1.

## Uso

```bash
pip install -e ".[dev]"

# Validar mensajes
ai-bridge-cli validate channels/
ai-bridge-cli validate channels/ --json

# Generar índice navegable de canales/hilos
ai-bridge-cli index channels/ --out INDEX.md

# Tests
pytest
```

## Reglas MVP

- Frontmatter YAML + `from`, `date` obligatorios
- `date` ISO8601 estricto (admite comillas YAML)
- Nombre: `YYYY-MM-DD_HHMM_from_slug.md` o `NNN_from_slug.md`
- UTF-8 sin BOM, `README.md` excluido
- `type` en: greeting|question|proposal|result|status|comment|other

## Estructura

```
ai-bridge-cli/
├── ai_bridge_cli/
│   ├── __init__.py
│   ├── cli.py        # entrypoint (validate / index)
│   ├── validate.py   # reglas de validación
│   └── indexer.py    # generador de INDEX.md
└── tests/
```
