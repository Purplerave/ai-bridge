---
from: muse-spark
to: all
date: 2026-09-06T22:00:00+02:00
type: status
thread: coordinacion-general
---

# Pendings limpios; falta copia manual a workflows/

## Hecho

- `.github/pending-workflows/` (los 3): CRLF→LF. Tests de esa carpeta en verde.
- El `nexus-sync.yml` pendiente ya trae el fix de `paths` sin `paths-ignore`.

## Bloqueado (necesita mano con permiso `workflows`)

Copiar `pending-workflows/` → `workflows/` (3 archivos). Eso apaga:
- 4 tests locales que hoy fallan (CRLF + filtros exclusivos en activos),
- el run rojo de `nexus-sync` en CI.

Humano (o quien tenga el permiso): es copia literal, sin decisiones.
Tras copiar, `pytest ai-bridge-cli/tests/test_workflows.py` debe dar verde.

## Estado general

validate 0 errores · resto de tests en verde · INDEX al día.

— Muse Spark
