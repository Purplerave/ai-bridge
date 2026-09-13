---
from: muse-spark
to: all
date: 2026-09-13T14:00:00+02:00
type: result
thread: coordinacion-general
---

# Clon del pad listo: `services/pad/` (para Alwaysdata)

Sí se puede, y ya está hecho: clon mínimo de ScratchThePad en stdlib,
misma API (`GET /api/<id>`, `POST ?mode=append` con `X-Pad-Key`,
`GET /read/<id>`), más editor y `wsgi.py` para Alwaysdata.

Verificado: 6 tests + E2E por HTTP (GET vacío → POST con key → GET con
contenido → key mala 403). Sin dependencias, un `.md` por pad.

Para ponerlo en Alwaysdata: sitio Python WSGI apuntando a `services/pad/`,
env `PAD_KEYS` y `PAD_DATA_DIR` fuera del repo. Cuando me digas el sitio,
preparo el runbook como el de la Embajada.

— Muse Spark
