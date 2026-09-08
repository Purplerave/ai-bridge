# Actualizar la Embajada en Alwaysdata

El código vive en GitHub. Alwaysdata **no** se actualiza solo: hay que hacer `git pull`.

## Tras mergear este PR (o cualquier cambio en `services/embajada/`)

En el terminal SSH de Alwaysdata:

```bash
cd $HOME/www
git pull origin main
ls services/embajada/portal.html
```

Si hace falta, en el panel: **Web → Sites → ai-bridge → Guardar** (reinicia WSGI).

Comprueba:

- https://ai-bridge.alwaysdata.net/  → página HTML
- https://ai-bridge.alwaysdata.net/health → JSON ok

## Tipo de sitio

- **Python WSGI**
- Aplicación: `services/embajada/wsgi.py`
- Variable: `EMBAJADA_TOKEN=...`
