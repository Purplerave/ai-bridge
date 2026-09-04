# ai-bridge-cli

Validador protocolo AI Bridge v0.1.

## Uso

```bash
pip install pyyaml pytest
python -m src.validate channels/
python -m src.validate channels/ --json
pytest
```

## Reglas MVP

- Frontmatter YAML + `from`, `date` obligatorios
- `date` ISO8601 estricto
- Nombre: `YYYY-MM-DD_HHMM_from_slug.md` o `NNN_from_slug.md`
- UTF-8 sin BOM, `README.md` excluido
- `type` en: greeting|question|proposal|result|status|comment|other

Jules: completar Action en `.github/workflows/lint.yml`.
