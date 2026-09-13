# Pad compartido (clon ScratchThePad, stdlib)

Un `.md` por pad en `data/`. Sin dependencias.

| Ruta | Qué |
|------|-----|
| `GET /api/<id>` | texto del pad |
| `POST /api/<id>?mode=append` + `X-Pad-Key` | añade al final |
| `GET /read/<id>` | vista HTML |
| `GET /` | editor mínimo |
| `GET /health` | ok |

Env: `PAD_DATA_DIR`, `PAD_KEYS="id:key,..."` (sin key = abierto, solo dev),
`PAD_HOST`, `PAD_PORT`. WSGI: `wsgi.py` (Alwaysdata).

Tests: `pytest services/pad` (6).
