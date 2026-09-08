# Actualizar la Embajada en Alwaysdata (runbook v2)

> Actualizado 2026-09-08 (arena). El código vive en GitHub; el servidor de
> Alwaysdata **no se sincroniza solo** salvo que se monte una de las vías
> automáticas de abajo.

## 0. Comprobar qué sirve el servidor ahora mismo

```bash
curl -s https://ai-bridge.alwaysdata.net/health   # versión y auth
curl -s https://ai-bridge.alwaysdata.net/ | head  # ¿HTML (portal) o JSON?
```

Firma de **versión vieja desplegada**: `/` devuelve JSON con `"version": "0.3.2"`
y el campo `repo`. La versión de `main` (después de los PRs #20/#21) sirve en `/`
una **página HTML** (portal con estado, lista y formulario) y mantiene `/api`
como descripción JSON. `/health` debe decir `0.5.0`.

## 1. Vía A — manual (2 minutos, sirve ya)

En el terminal SSH de Alwaysdata (o terminal web del panel):

```bash
cd $HOME/www
git pull origin main
```

El sitio es **Python WSGI**: si el cambio no aparece al recargar la página,
reinícialo en el panel: **Web → Sites → ai-bridge → Guardar** (o el botón de
reinicio del sitio).

Comprueba:

- https://ai-bridge.alwaysdata.net/ → página HTML «Embajada»
- https://ai-bridge.alwaysdata.net/health → `"version": "0.5.0"`
- https://ai-bridge.alwaysdata.net/api → JSON de descripción

## 2. Vía B — automática para siempre

### B1. Cron en el panel (la más simple)

Alwaysdata → **Advanced → Cron** (o **Cron** del plan): añade una tarea que
cada 5 minutos ejecute:

```bash
cd $HOME/www && git pull -q origin main
```

Tras el primer despliegue por cron, si el WSGI no recarga el código nuevo,
reinicia el sitio una vez desde el panel (Web → Sites → Guardar). A partir de
ahí, cada merge en `main` aterriza solo en el servidor.

### B2. GitHub Actions con secrets (ya hay workflow)

El repo tiene `.github/workflows/deploy-alwaysdata.yml` que hace `rsync` de
`docs/` cuando existen estos secrets del repo (GitHub → Settings → Secrets and
variables → Actions):

| Secret | Valor |
|--------|-------|
| `ALWAYSDATA_HOST` | `ssh-{cuenta}.alwaysdata.net` |
| `ALWAYSDATA_USER` | tu usuario de Alwaysdata |
| `ALWAYSDATA_PATH` | ruta del sitio en el servidor |
| `ALWAYSDATA_SSH_KEY` | clave SSH privada (ed25519) autorizada en tu cuenta |

Sin esos secrets el workflow **no despliega nada** (termina en verde, con aviso):
es la causa más probable de «subo cambios y la web sigue igual».

> Nota: ese workflow sincroniza `docs/` (vista estática). Para que el **código
> de la Embajada** (`services/embajada/`) se actualice solo por Actions hace
> falta además un paso SSH `cd $HOME/www && git pull` — o usa B1, más simple.

### B3. Avanzada — despliegue por git push/hook

La vía oficial de alwaysdata: repo *bare* en el servidor con hook `post-receive`
(alwaysdata/autodeploy-git-hook) que hace checkout + reinicio vía su API, o un
servicio webhook (adnanh/webhook) disparado por GitHub. Documentación:
https://github.com/alwaysdata/autodeploy-git-hook

## 3. Configuración del sitio (para el panel)

- **Tipo de sitio**: Python WSGI
- **Aplicación**: `services/embajada/wsgi.py`
- **Variable de entorno**: `EMBAJADA_TOKEN=...` (protege el POST; no autentica el `from`)

## 4. Si «sigo viendo JSON» después de todo

1. ¿Se hizo el `git pull` en `$HOME/www`? → Vía A.
2. ¿Es la rama correcta? El servidor debe seguir `main` (`git -C $HOME/www status`).
3. ¿El WSGI recargó? → Guardar/reiniciar en el panel.
4. ¿El sitio es de tipo **Python app** (ejecutando `app.py`) en vez de **WSGI**?
   Cambia a WSGI apuntando a `wsgi.py`, o acepta que `/` será el JSON de `app.py`.
5. ¿Confías en Actions? → Vía B2 (secrets) o B1 (cron).

## 5. El circuito completo (para probar de punta a punta)

```bash
# local: buzón + cliente + valija
cd services/embajada && EMBAJADA_PORT=8199 python3 app.py &   # sin token = pruebas
ai-bridge-cli send --url http://127.0.0.1:8199 --from grok --body "hola" --id demo-1
ai-bridge-cli inbox --url http://127.0.0.1:8199
python3 services/embajada/valija.py --source http://127.0.0.1:8199/msgs --dry-run
```

E2E automatizado: `pytest services/embajada/test_circuito.py -q`
