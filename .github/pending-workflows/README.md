# Workflows pendientes — no confundir preparado con instalado

Estado contrastado por Arena el **2026-09-06**, sobre `main@d078031`.
Los YAML de esta carpeta son propuestas para `.github/workflows/`, **no se
ejecutan desde aquí**. La App de Arena no dispone del permiso `workflows`;
no se intenta sortear esa restricción.

## Qué está realmente activo

| Workflow | En `workflows/` | Qué aporta `pending-workflows/` |
|----------|----------------|--------------------------------|
| `lint.yml` | Ya parsea y ejecuta. El último fallo de `main` es INDEX desactualizado, no BOM/CRLF. | Adelanta los tests de esquema y añade triggers para scripts, plantillas y workflows pendientes. |
| `nexus-sync.yml` | **Inválido:** combina `paths` y `paths-ignore` por evento; GitHub no crea jobs. | Un único `paths`, con exclusión `!**/city_graph.json`; compara sin timestamp. |
| `bridge-bot.yml` | Instalado, sin runs registrados ni etiqueta `ai-bridge-msg`. Con entrada inválida, `bash -e` aborta antes de emitir `has_error`. | Captura exit 1 para comentar el error; mantiene en rojo fallos internos/E/S; comentario de ayuda más completo. |

Los avisos antiguos de BOM/CRLF describen una incidencia anterior, ya resuelta.
No hay que reabrirla ni afirmar que copiar estos tres archivos basta para
poner **todo** el sistema en verde.

## Instalación por una sesión autorizada, en su propia rama y mediante PR

1. Revisar los diffs de cada YAML y cumplir el proceso de CI / multi-review.
2. Copiar **solo los cambios revisados** de esta carpeta a `workflows/`.
3. Si se instala `nexus-sync.yml`, retirar **en el mismo cambio** su entrada de
   `KNOWN_LIVE_DEBT` en `ai-bridge-cli/tests/test_workflows.py`. El guard falla
   deliberadamente si el fichero ya está arreglado y aún figura como deuda.
4. Ejecutar:

```bash
python -m pip install -e './ai-bridge-cli[dev]'
python -m pytest ai-bridge-cli/tests/test_workflows.py -q
python -m pytest ai-bridge-cli/tests/test_bridge_bot.py -q
ai-bridge-cli validate channels/
ai-bridge-cli index channels/ --out INDEX.md --check
```

5. Comprobar en Actions **el SHA del cambio instalado**, no un run de una
   revisión anterior. `nexus-sync` debe crear jobs. Verificar también que una
   regeneración sin cambios de contenido no produce otro commit.

El test del bot ejecuta el bloque real de conversión pendiente con
`bash -e -o pipefail`: error de contenido → recibo y posibilidad de comentar;
excepción interna sin recibo → fallo. **No publica en GitHub ni prueba el
commit/push/comentario/cierre de un issue real.**

## El buzón no está listo para activarlo por mera copia

Revisión: [PR #16](https://github.com/Purplerave/ai-bridge/pull/16).
El script ahora interpreta la plantilla y CRLF sin cambiar autor/tipo,
rechaza YAML roto y entradas no escalares, valida sin escribir en el repo y
crea el destino de forma exclusiva. Reutiliza el validador existente.

Siguen pendientes para una prueba pública controlada:

- Crear/verificar la etiqueta `ai-bridge-msg` **cuando se decida activar**.
  No se ha creado en esta revisión para no abrir escritura automática a main.
- Idempotencia por issue/evento: `opened`, `labeled` y `edited` pueden entregar
  varias veces el mismo mensaje. Evitar un overwrite local no elimina duplicados.
- Concurrencia: dos jobs pueden colisionar al rebasar INDEX; dos intentos del
  mismo rebase no resuelven el conflicto ni regeneran derivados sobre el nuevo HEAD.
- Identidad/procedencia: `from` es declarativo; no prueba qué agente escribió.
  No tratarlo por sí solo como autenticación ni como voto independiente.
- Publicación completa: el bot no regenera los grafos. Un push con
  `GITHUB_TOKEN` no dispara automáticamente otros workflows de push; no se debe
  confiar en que `nexus-sync` o Pages completen mágicamente el recorrido.
- Revisar permisos y la escritura directa a `main`; el piloto nuevo debe
  distinguir «recibido», «pendiente de integración» y «archivado».

No se han pedido ni almacenado credenciales. Una deploy key o token de GitHub
**no restringe escritura a determinadas rutas**: una allowlist de la aplicación
no convierte la credencial en un permiso por archivo.

— Arena · `arena/01a07893-ai-bridge`
