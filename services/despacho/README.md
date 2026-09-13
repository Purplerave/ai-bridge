# Despacho: Embajada + pad en un solo puerto

`serve.py`: `/pad/*` → pad, resto → Embajada. IPv6 dual-stack (Alwaysdata).
`wsgi.py`: variante WSGI (si el sitio es tipo WSGI en vez de programa).

Alwaysdata (tipo **Programa de usuario**), comando:

```sh
sh -c 'export EMBAJADA_PORT=$PORT; exec python3 services/despacho/serve.py'
```

Env: las de la Embajada (`EMBAJADA_TOKEN`…) + `PAD_KEYS="mesa:clave"` +
`PAD_DATA_DIR=/home/tuusuario/data/pads`. Directorio de trabajo: `www/`.

Tests: `pytest services/despacho services/pad` (12).
