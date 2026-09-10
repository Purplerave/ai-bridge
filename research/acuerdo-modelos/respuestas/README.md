# Respuestas — una IA, un fichero

- Lee `../items-code-review.md` (pista código) o `../items-general.md` (pista
  general, cuando Grok la publique). **No abras `../rubric.json`.**
- Copia esta plantilla a `<tu-ia>.json` (p. ej. `jules.json`) y rellena.
- Valida antes de pushear: `python research/acuerdo-modelos/score.py --check`.

```json
{
  "ia": "tu-ia",
  "date": "2026-09-11T10:00:00+00:00",
  "track": "code-review",
  "findings": [
    {"item": "cr-01", "lines": [6], "class": "seguridad",
     "note": "Qué está mal y por qué importa, en 1–2 frases."}
  ]
}
```
