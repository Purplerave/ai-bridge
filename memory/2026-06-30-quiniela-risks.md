# Session: 2026-06-30 22:04:22 UTC

- **Session Key**: agent:main:main
- **Session ID**: 31d3996d-821a-4e60-9602-0a32d9b08d32
- **Source**: webchat

## Conversation Summary

user: Responde solo: NARA_OK
user: Responde solo: NARA_OK
user: Responde solo: NARA_OK
user: Responde solo: NARA_OK
assistant: NARA_OK
user: Responde solo: NARA_OK
assistant: NARA_OK
user: Sender (untrusted metadata):
```json
{
  "label": "openclaw-control-ui",
  "id": "openclaw-control-ui"
}
```

[Tue 2026-06-30 23:08 GMT+2] Buen trabajo. Codex ha revisado tus 5 hallazgos contra el codigo real.

Siguiente tarea:
Revisa riesgos reales de producto y fiabilidad en:
1. guardado/edicion de quinielas,
2. actualizacion de resultados en directo,
3. cierre de jornada y bloqueo de edicion,
4. calculo de aciertos con dobles/triples y pleno al 15,
5. coherencia entre datos Q15, Highlightly y base SQLite.

No repitas puntos ya tratados. Prioriza bugs que puedan hacer perder quinielas, mostrar resultados incorrectos o calcular mal puntos.

Formato:
MiMo dice:
Riesgo:
Evidencia en archivo/funcion:
Solucion propuesta:
Severidad:
'@
assistant: OK, he analizado a fondo el código completo. Aquí van los riesgos reales que encontré:

---

## MiMo dice:

### Riesgo 1: Cierre de jornada falla si faltan horas de partido
**Evidencia:** `app.py:2296-2306` — `save_predictions()`
```python
kickoff_times = []
for row in rows:
    kickoff_at = parse_madrid_datetime(row["fecha"], row["hora"])
    if kickoff_at:
        kickoff_times.append(kickoff_at)
first_kickoff = min(kickoff_times) if kickoff_times else None
close_at = first_kickoff - timedelta(minutes=max(0, PREDICTION_CLOSE_MINUTES_BEFORE_KICKOFF)) if first_kickoff else None
already_closed = bool(close_at and madrid_now() >= close_at)
already_closed = already_closed or any(
    is_scored_status(row["status"]) or is_live_scored_status(row["status"])
    for row in rows
)
```
Si `parse_madrid_datetime` devuelve `None` para algún partido (fecha u hora vacía, formato inesperado de la BD), `first_kickoff` puede ser `None` o una hora incorrecta. Si es `None`, `close_at` es `None` y el cierre por tiempo no se aplica. La única protección es el check de status, que depende de Highlightly haber actualizado el partido a "LIVE"/"FT" — si Highlightly va lago o falla, **un usuario podría guardar/editar su quiniela después del inicio real del primer partido**.

**Solución:** Añadir un fallback: si `first_kickoff` es `None` pero hay partidos con `fecha` válida (aunque `hora` sea "-"), usar la fecha como cierre. Además, loggear warning cuando no se pueda calcular `close_at` para una jornada activa.

**Severidad:** 🔴 ALTA — puede perder quinielas

---

### Riesgo 2: Match atascado en LIVE bloquea la jornada para siempre
**Evidencia:** `app.py:2308-2313` — `save_predictions()` ya usa `is_scored_status` / `is_live_scored_status`, pero `app.py:1776` (endpoint `/api/liga/data`) usa:
```python
is_locked = first_kickoff_started or any((m.get('status') or '') in ('LIVE', 'FT', 'FINISHED') for m in partidos)
```
Y en `quantum_final.js:480-482`:
```python
function isImplicitlyFinished(match) {
    const minute = matchMinuteValue(match);
    return Boolean(score && minute >= 105);
}
```
Si Highlightly devuelve un partido con status "LIVE" pero el minuto se queda atascado (ej: sigue mostrando minuto 78 aunque el partido terminó), el partido nunca pasa a "FT". La jornada queda bloqueada (`is_locked = true`) y nadie puede editar la quiniela de la siguiente jornada si esa se superpone. Además, `isImplicitlyFinished` solo actúa en el frontend, no en el backend.

**Solución:** Añadir un timeout en backend: si un partido lleva más de 3h con status "LIVE" y no se actualiza, marcarlo como "STALE" o permitir que `compute_refresh_window` lo trate como terminado. En frontend, usar `isImplicitlyFinished` también para el `is_locked` del backend.

**Severidad:** 🔴 ALTA — puede bloquear jornadas indefinidamente

---

### Riesgo 3: Guardado DELETE+INSERT sin verificación atómica real
**Evidencia:** `app.py:2321-2348` — `save_predictions()`
```python
conn.execute("BEGIN IMMEDIATE")
conn.execute("DELETE FROM predicciones WHERE user_id = ? AND jornada = ?", (uid, target_jornada))
for i, signo in enumerate(normalized_signs, 1):
    if signo != "-":
        conn.execute("INSERT OR REPLACE INTO predicciones ...")
saved_rows = conn.execute("SELECT ...").fetchall()
# verificación de read-back
if saved_signs != normalized_signs:
    conn.rollback()
```
La verificación de read-back es buena, pero hay un problema: `normalized_signs` es una lista Python con strings como "1", "X2", "M-1". `saved_signs` se construye leyendo de SQLite. Si SQLite almacena "X2" pero Python compara con "X2" usando `!=`, debería funcionar... **PERO** hay un edge case: si el usuario envía "X2" con espacios (ej: "X 2"), `normalize_prediction_sign` lo normaliza a "X2", pero si por algún motivo la comparación falla (encoding, whitespace), el rollback se dispara falsamente y el usuario pierde su quiniela.

Más importante: el rate limit de 5 segundos (`is_rate_limited("predicciones_save", user.get("id"), 5)`) no protege contra dos requests simultáneos (ej: doble click rápido que ambos pasan el rate check antes de que se actualice el timestamp).

**Solución:** Usar `INSERT OR REPLACE` directamente sin DELETE previo (ya lo hace), y eliminar el DELETE redundante. Además, usar `SELECT ... WHERE user_id = ? AND jornada = ? ORDER BY partido_id` directamente como fuente de verdad en vez de comparar con la lista del request.

**Severidad:** 🟡 MEDIA — puede perder quinielas en casos edge

---

### Riesgo 4: Q15 scraper puede cerrar jornada con datos incorrectos
**Evidencia:** `SCRAPE_QUINIELA15_DIRECTO.py:73-78`:
```python
def status_for_q15(score_home, score_away, minute, text):
    if minute:
        return "HT" if str(minute).lower().startswith("descanso") else "LIVE"
    if score_home is None or score_away is None:
        return "NS"
    return "FT" if has_final_signal(text) else "STALE"
```
Y `has_final_signal`:
```python
def has_final_signal(text):
    return bool(re.search(r"\b(finalizado|terminado|final|ft|fin)\b", text, flags=re.I))
```
Si el scraper Q15 detecta un marcador (score_home no es None) pero no encuentra la señal "finalizado" en el texto, devuelve "STALE". El problema: "STALE" no es un status reconocido por `is_scored_status` ni `is_live_scored_status`, así que el partido queda en un limbo — ni cerrado ni abierto. Si luego Highlightly devuelve el partido como "FT" pero con un marcador diferente (por delay), hay inconsistencia.

Además, el scraper no tiene ninguna verificación de que los equipos scrapeados coincidan con los de la BD. Si la web cambia el orden de los partidos o el scraper parsea mal un nombre, los goles se asignan al partido equivocado.

**Solución:** Añadir validación cruzada: comparar equipos del scraper con equipos de la BD antes de actualizar. Añadir "STALE" a los statuses reconocidos o tratarlo como "NS" para que Highlightly pueda sobreescribirlo.

**Severidad:** 🟡 MEDIA — puede mostrar resultados incorrectos

---

### Riesgo 5: `puntos_acumulados` se suma dos veces al ranking
**Evidencia:** `app.py:1637-1647` — ranking calculation en `get_liga_data()`:
```python
extra_users = conn.execute("SELECT id, puntos_acumulados FROM usuarios").fetchall()
extra_points = {}
for u in extra_users:
    uid = canonical_contest_id(u['id'])
    extra_points[uid] = max(int(extra_points.get(uid, 0) or 0), int(u['puntos_acumulados'] or 0))
for uid, points in extra_points.items():
    if uid not in ranking:
        ranking[uid] = {"total": points, "bonus": points, ...}
    else:
        ranking[uid]["bonus"] = points
        ranking[uid]["total"] += points
```
Y en `_build_contest_payload_uncached()` (línea ~2072) se hace exactamente lo mismo. Si ambas funciones se llaman para construir el ranking (una para la API de liga, otra para el contest), **los puntos se suman dos veces** en diferentes contextos. Además, `extra_points` usa `max()` para deduplicar por `canonical_contest_id`, pero si un usuario tiene múltiples IDs canónicos diferentes (ej: "GEMINI" y "gemini"), cada uno suma por separado.

**Solución:** Centralizar el cálculo de ranking en una sola función y cachear el resultado. Usar `canonical_contest_id` consistentemente en todas las queries.

**Severidad:** 🟡 MEDIA — muestra puntos incorrectos en el ranking

---

### Resumen de prioridad:
1. 🔴 **Riesgo 1** (cierre falla sin hora) — el más crítico, puede hacer perder quinielas
2. 🔴 **Riesgo 2** (match atascado en LIVE) — bloquea jornadas
3. 🟡 **Riesgo 3** (guardado no atómico) — edge case de pérdida
4. 🟡 **Riesgo 4** (Q15 scraper inconsistente) — resultados incorrectos
5. 🟡 **Riesgo 5** (doble suma de puntos) — ranking incorrecto
user: Sender (untrusted metadata):
```json
{
  "label": "openclaw-control-ui",
  "id": "openclaw-control-ui"
}
```

[Tue 2026-06-30 23:16 GMT+2] Codex ha revisado tu informe anterior.

Aplicado:
- Cierre de quiniela con fallback por fecha si falta hora.
- Misma lógica de cierre en /api/liga/data y /api/predicciones/save.
- Validación de equipos Q15 vs BD antes de actualizar marcador.

No aplicado:
- LIVE atascado: el collector ya lo detecta y una jornada empezada debe seguir cerrada.
- DELETE+INSERT: está dentro de BEGIN IMMEDIATE y con read-back.
- Doble suma de puntos: son payloads separados, no se combinan.

Siguiente tarea:
Revisa ahora solo estos bloques:
1. cálculo de aciertos y ranking,
2. pleno al 15,
3. dobles/triples,
4. premios/galardones,
5. perfil del usuario y estadísticas.

Busca bugs reales que puedan:
- calcular mal puntos,
- premiar al ganador equivocado,
- mostrar una posición incorrecta,
- romper el pleno al 15,
- mezclar usuarios humanos con IAs ocultas.

No repitas problemas ya tratados.
No propongas refactors grandes si no hay bug claro.

Formato obligatorio:
MiMo dice:
Riesgo:
Evidencia en archivo/función:
Por qué importa:
Solución mínima:
Severidad:
'@
assistant: OK, encontré los bugs reales. Aquí van:

---

**MiMo dice:**

**Riesgo 1: `get_user_stats` busca por `user_id` crudo, no canónico — estadísticas vacías para usuarios migrados**
Evidencia en archivo/función: `app.py:2524` — `get_user_stats()`
```python
rows = conn.execute("""
    SELECT p.jornada, p.partido_id, p.signo, r.signo_actual, ...
    FROM predicciones p
    JOIN resultados r ON p.jornada = r.jornada AND p.partido_id = r.partido_id
    WHERE p.user_id = ?
    ORDER BY p.jornada, p.partido_id
""", (uid,)).fetchall()
```
Compara con el ranking en `_build_contest_payload_uncached` (línea 2158) que sí usa `canonical_contest_id(p['user_id'])`. Si un usuario tiene predicciones antiguas guardadas como `v260_omnisciente` pero consulta stats con `programa`, la query no las encuentra. El ranking las cuenta bien porque deduplica por ID canónico, pero `/api/user/stats` devuelve 0 aciertos.
Por qué importa: Un usuario humano ve sus estadísticas en 0 aunque tiene aciertos reales. Pierde confianza en la app.
Solución mínima: Añadir `canonical_contest_id(uid)` y buscar por ambos IDs:
```python
canonical = canonical_contest_id(uid)
# ... query con WHERE p.user_id IN (?, ?)  (uid, canonical)
```
Severidad: 🟡 MEDIA

---

**Riesgo 2: `profile["hits"]` incluye `puntos_acumulados` (bonus) — tasa de acierto inflada**
Evidencia en archivo/función: `app.py:2177-2180` y `app.py:2222-2223`
```python
# Línea 2177: bonus se suma a totals
for uid, points in extra_points.items():
    if uid.lower() not in hidden_ids and points:
        totals[uid] = totals.get(uid, 0) + points

# Línea 2222: hit_rate usa totals (que incluye bonus)
total_hits = int(mine["points"] if mine else 0)  # mine viene de rows_from_scores(totals)
"hit_rate": round((total_hits / total_predictions) * 100, 2) if total_predictions else 0,
```
`mine["points"]` es `totals[uid]` que = aciertos reales + puntos bonus. `total_predictions` = jornadas × 15. Si un usuario tiene 5 puntos bonus y 50 aciertos en 5 jornadas: `(55 / 75) * 100 = 73.3%` cuando debería ser `(50 / 75) * 100 = 66.7%`.
Por qué importa: El perfil muestra una tasa de acierto mayor a la real. En competiciones, esto puede hacer que un usuario aparezca como "mejor" de lo que es.
Solución mínima: Calcular `total_hits` sin bonus:
```python
user_finished_hits = sum(jornada_scores.get(j, {}).get(uid, 0) for j in jornada_scores)
total_hits = user_finished_hits  # sin extra_points
```
Severidad: 🟡 MEDIA

---

**Riesgo 3: Empates en jornadas/meses rompen premios — dos usuarios con mismos puntos, solo uno es "ganador"**
Evidencia en archivo/función: `app.py:2232-2238` (galardones) y `app.py:2196` (sort)
```python
rows.sort(key=lambda item: (-item["points"], item["name"]))
for idx, item in enumerate(rows, 1):
    item["pos"] = idx
```
Y en galardones:
```python
winner = rows[0] if rows else None
```
Si dos usuarios tienen 12 aciertos en una jornada, el que gana es el que tiene el nombre alfabéticamente primero (porque el sort secundario es `item["name"]`). Ej: "ALICE" gana sobre "BOB" siempre, independientemente de quién acertó primero.
Por qué importa: Los galardones muestran un único ganador cuando podría haber empate. Esto premia al equivocado si los puntos son iguales.
Solución mínima: Detectar empates y mostrar todos los empatados:
```python
if rows:
    top_score = rows[0]["points"]
    winners = [r for r in rows if r["points"] == top_score]
    # usar winners en vez de solo rows[0]
```
Severidad: 🟡 MEDIA

---

**Riesgo 4: Diferencia de puntuación "jornada" entre `/api/liga/data` y `/api/concurso` durante partidos en vivo**
Evidencia en archivo/función: `app.py:1633-1634` (ranking en liga/data) vs `app.py:2168-2170` (contest payload)
```python
# Liga/data: incluye LIVE en jornada
if str(p['jornada']) == str(j) and score_prediction(p['partido_id'], p['signo'], current_real):
    ranking[uid]["jornada_live"] += 1
# ... luego:
stats["jornada"] = stats.get("jornada_live", 0)  # ← incluye partidos LIVE

# Contest payload: solo FT
if not is_scored_status(row["status"]):  # ← excluye LIVE
    continue
```
Durante un partido en directo, el ranking en la pantalla principal puede mostrar "PROGRAMA: 8 aciertos" mientras que el perfil/concurso muestra "PROGRAMA: 5 aciertos" (solo los finalizados).
Por qué importa: Confusión al usuario. Puede pensar que hay un bug o que le están robando puntos.
Solución mínima: Documentar en la UI que el ranking en vivo es provisional, o unificar la lógica usando un campo `jornada_provisional` separado.
Severidad: 🟢 BAJA (cosmético, pero confunde)

---

**Riesgo 5: `hit_rate` cuenta predicciones de jornadas parcialmente terminadas como si fueran 15/15**
Evidencia en archivo/función: `app.py:2218-2222`
```python
my_jornadas = []
for jornada in sorted(jornada_scores.keys()):
    rows = rows_from_scores(jornada_scores[jornada])
    found = next((item for item in rows if item["id"] == uid), None)
    if not found:
        continue
    # ...
    my_jornadas.append(...)

total_predictions = len(my_jornadas) * 15
```
Si una jornada tiene solo 3 partidos finalizados (de 15), `jornada_scores[jornada]` tiene puntuaciones parciales. Pero `total_predictions` cuenta esa jornada como 15 predicciones. Resultado: `(3 aciertos en 3 partidos) / (15 predicciones) * 100 = 20%` cuando debería ser `100%`.
Por qué importa: La tasa de acierto se deprime artificialmente en jornadas en curso. Un usuario que acertó los 3 partidos jugados ve un 20% en vez de 100%.
Solución mínima: Contar predicciones reales evaluadas:
```python
evaluated = sum(1 for (uid2, j), signs in ballots.items()
                if uid2 == uid
                for pid in signs
                if results.get((j, pid)))
total_predictions = evaluated if evaluated else 1
```
Severidad: 🟡 MEDIA
user: Sender (untrusted metadata):
```json
{
  "label": "openclaw-control-ui",
  "id": "openclaw-control-ui"
}
```

[Tue 2026-06-30 23:27 GMT+2] $mensaje = @'
Rol:
Actua como OpenClaw, auditor externo independiente de Liga de Maestros.

Contexto:
- MiMo es otra IA externa distinta, de Xiaomi.
- Tu no eres MiMo.
- Codex es quien verifica contra el codigo real, aplica cambios y actualiza AUDITORIA/00_LEEME_AUDITORIA.md.
- Pablo es el jefe/product owner y decide prioridades.

No edites archivos directamente.

Cuando termines una revision, añade al final un bloque llamado:

PROPUESTA PARA 00_LEEME_AUDITORIA.md

Formato:
### NN. Revision OpenClaw - titulo breve

OpenClaw dice: resumen en una frase.

Codex deberia revisar:
- punto 1
- punto 2

Decision sugerida: aplicado / aplicado parcial / cola viva / no aplicar.

Motivo: breve.

Importante:
- No repitas puntos ya tratados por MiMo, OpenClaw o Codex.
- No hagas el documento largo.
- No afirmes que algo esta aplicado si Codex aun no lo ha aplicado.
- Si no estas seguro, marca "Codex deberia verificar".

Siguiente tarea:
Revisa la experiencia de usuario tras guardar quiniela, editar, salir/entrar, avisos/toasts, y estados de boton Guardar/Editar/Cerrada.
Busca bugs reales o mejoras pequeñas que eviten confusion al usuario.

Formato principal:
OpenClaw dice:
Riesgo:
Evidencia:
Solucion minima:
Severidad:

Y al final incluye PROPUESTA PARA 00_LEEME_AUDITORIA.md.
'@

openclaw agent --local --agent quinielas --message $mensaje
assistant: He analizado el flujo completo de UX: guardar → editar → salir/entrar → toasts → estados de botón. Aquí van los hallazgos reales:

---

**OpenClaw dice:**

**Riesgo 1: Botón "Guardar" no se desactiva durante el guardado — sin feedback visual**
Evidencia: `quantum_final.js:2265` (`state.savingTicket = true`) y `quantum_final.js:800-817` (`hydrateHero`):
```javascript
// hydrateHero no tiene en cuenta savingTicket
save.disabled = !canSave;  // solo mira canSave, no savingTicket
```
El flag `savingTicket` previene doble petición en `savePredictions()` (línea 2246), pero `hydrateHero()` nunca lo consulta. El botón sigue con su aspecto normal (no girando, no atenuado). Un usuario que hace click y no ve feedback inmediato puede pensar que no pasó nada y hacer click de nuevo (el segundo click se ignora silenciosamente por `savingTicket`).
Solución mínima: Añadir `save.disabled = !canSave || state.savingTicket` en `hydrateHero()`, y opcionalmente cambiar el texto a "Guardando..." mientras `savingTicket` es true.
Severidad: 🟡 MEDIA

---

**Riesgo 2: Botón muestra "Cerrada" antes de cargar datos — falso positivo**
Evidencia: `quantum_final.js:807-812`:
```javascript
const canSave = String(state.data.jornada) === String(state.data.max_jornada) && !state.data.is_locked;
save.disabled = !canSave;
if (!canSave) {
    save.textContent = "Cerrada";
}
```
Si `state.data` es `null` (carga inicial pendiente o error de red), `canSave` es `false` y el botón muestra "Cerrada" deshabilitado. El usuario interpreta que la jornada está cerrada cuando en realidad los datos no han llegado aún.
Solución mínima: Comprobar `state.data` antes de evaluar `canSave`:
```javascript
if (!state.data) {
    save.textContent = "Cargando...";
    save.disabled = true;
} else if (!canSave) {
    save.textContent = "Cerrada";
    save.disabled = true;
}
```
Severidad: 🟡 MEDIA

---

**Riesgo 3: Guardar requiere dos clicks sin aviso claro — UX confusa para usuario nuevo**
Evidencia: `quantum_final.js:2259-2263`:
```javascript
if (hasSavedTicket() && !state.editMode && !state.draftDirty) {
    state.editMode = true;
    hydrateHero();
    return showToast(`Puedes editar hasta ${state.data.edit_deadline || "el inicio del primer partido"}.`);
}
```
Un usuario que ya guardó una quiniela y vuelve a hacer click en el botón (que dice "Editar quiniela") no guarda — primero entra en modo edición, luego tiene que volver a hacer click para guardar. El toast "Puedes editar hasta..." explica el flujo, pero si el usuario no lee el toast (o si el toast se pierde entre otros), piensa que el botón no funciona.
Solución mínima: Cambiar el texto del botón a "Editar y guardar" o añadir un tooltip en el botón que explique el flujo de dos pasos. Alternativamente, entrar en modo edición automáticamente al hacer cualquier cambio en los signos, en vez de requerir un click previo.
Severidad: 🟢 BAJA (intencional, pero mejorable)

---

**Riesgo 4: Borrador localStorage persiste entre sesiones y puede confundir al volver**
Evidencia: `quantum_final.js:964-975`:
```javascript
function draftKey() {
    const owner = state.user?.id || "anon";
    const jornada = state.data?.jornada || state.jornada || "actual";
    return `liga_maestros_borrador_${owner}_${jornada}`;
}
```
Y `quantum_final.js:1073-1076`:
```javascript
const draft = readDraft();
state.my_signs = draft || serverSigns;
state.draftDirty = Boolean(draft && !sameSigns(draft, serverSigns));
```
Si un usuario hace cambios (draftDirty = true), cierra el navegador sin guardar, y vuelve al día siguiente, el borrador se restaura automáticamente. Esto es *bueno* en general, pero hay un caso problemático: si la jornada ya cerró mientras el usuario no estaba, el borrador se carga igualmente, `draftDirty` es `true`, y el botón muestra "Guardar cambios" (no "Cerrada"). Al hacer click, el servidor rechaza con "La quiniela ya esta cerrada", pero la UX sugiere que se puede guardar.
Solución mínima: Después de cargar el draft, comprobar `is_locked`. Si está cerrada, forzar `draftDirty = false` y `editMode = false` para que `hydrateHero` muestre "Cerrada" correctamente.
Severidad: 🟡 MEDIA

---

**Riesgo 5: Error del servidor deja `editMode = true` pero botón no lo comunica bien**
Evidencia: `quantum_final.js:2288-2291`:
```javascript
} catch (error) {
    showToast(error.message, "error");
} finally {
    state.savingTicket = false;
}
```
Si el guardado falla (error 500, red caída), `editMode` sigue en `true` y `draftDirty` sigue en `true`. El botón muestra "Guardar cambios" y el usuario puede reintentar, lo cual es correcto. Pero no hay ningún indicador visual de que hubo un error más allá del toast (que desaparece en 9 segundos). Si el usuario no ve el toast, piensa que todo está bien.
Solución mínima: Añadir una clase CSS al botón (ej: `is-error`) durante unos segundos tras un fallo, o mantener un banner persistente de error hasta el próximo intento.
Severidad: 🟢 BAJA

---

**PROPUESTA PARA 00_LEEME_AUDITORIA.md**

### 06. Revision OpenClaw - UX post-guardado y estados de boton

OpenClaw dice: El flujo de guardar/editar funciona correctamente en lógica, pero tiene 5 problemas de UX que pueden confundir al usuario — especialmente la falta de feedback durante el guardado y el botón "Cerrada" prematuro.

Codex debería revisar:
- Añadir `state.savingTicket` a la condición de `save.disabled` en `hydrateHero()` y mostrar "Guardando..." durante el guardado.
- Comprobar `state.data !== null` antes de mostrar "Cerrada" en el botón.
- Después de cargar un draft, comprobar `is_locked` y forzar `draftDirty = false` si la jornada está cerrada, para que el botón muestre "Cerrada" en vez de "Guardar cambios".
- Considerar entrar en modo edición automáticamente al primer cambio de signo, eliminando el click previo de "Editar quiniela".

Decision sugerida: aplicado parcialmente (los puntos 1 y 2 son fixes rápidos de una línea; el punto 4 es más opinable).

Motivo: Los puntos 1 y 2 previenen confusión real (usuario piensa que el botón no funciona o que la jornada está cerrada cuando no lo está). El punto 3 previene intentos de guardado en jornada cerrada. El punto 4 es una mejora de UX pero cambia el flujo intencional.
user: Sender (untrusted metadata):
```json
{
  "label": "openclaw-control-ui",
  "id": "openclaw-control-ui"
}
```

[Tue 2026-06-30 23:32 GMT+2] $mensaje = @'
Actua como OpenClaw, asesor tecnico-producto de Liga de Maestros.

Ya no busques bugs. Quiero mejoras implementables.

Mira el proyecto desde el punto de vista de:
- impacto para usuario,
- dificultad tecnica,
- reutilizacion de datos que ya existen,
- bajo riesgo de romper la app.

Propón mejoras para:
1. Perfil del usuario.
2. Logros semanales/mensuales.
3. Ranking y comparativas.
4. Directo/resultados.
5. Guardado/edicion de quiniela.
6. Explicacion de consenso IA/La Peña.
7. Contenido entre jornadas.

Formato:
Mejora:
Archivos o datos que aprovecharia:
Implementacion minima:
Impacto:
Dificultad:
Prioridad:

No busques bugs. No repitas auditorias anteriores. No edites archivos.
'@

openclaw agent --local --agent quinielas --message $mensaje
assistant: He analizado el código existente en profundidad. Aquí van las mejoras priorizadas por impacto/esfuerzo:

---

**Mejora 1: Racha actual y mejor racha del usuario en el perfil**
Archivos o datos que aprovecharía: `profile.results` (ya calculado en `profile_for`), `jornada_scores` (ya existe). Solo hay que iterar sobre `results` y contar jornadas consecutivas con aciertos ≥ N.
Implementación mínima: En `profile_for()` (app.py ~2211), después de calcular `my_jornadas`, iterar hacia atrás contando jornadas consecutivas con `points >= 7`. Añadir `{"current_streak": N, "best_streak": N}` al JSON del perfil. En JS, mostrar como dos números en `profile-grid`.
Impacto: Alto. Las rachas son el motivador #1 en apps de quinielas (ver LaLiga Fantasy, Marca Quiniela). Dato gratuito que ya existe.
Dificultad: Muy baja. 10 líneas Python, 2 líneas HTML.
Prioridad: 🔴 ALTA

---

**Mejora 2: "Me vs La Peña" — comparativa personal contra el consenso**
Archivos o datos que aprovecharía: `consenso` tabla (ya existe, tiene `ganador` por partido), `ballots` (ya tiene las predicciones del usuario), `results` (ya tiene resultados reales).
Implementación mínima: En `profile_for()`, para cada jornada jugada, comparar el ticket del usuario contra el consenso de esa jornada. Calcular: (a) cuántas veces el usuario superó a La Peña, (b) cuántas veces coincidieron, (c) cuántas veces La Peña fue mejor. Añadir `{"vs_pena": {"wins": N, "draws": N, "losses": N, "avg_diff": +1.2}}` al perfil.
Impacto: Alto. Los usuarios quieren saber si son mejores que "el grupo". Es el hook competitivo más fuerte.
Dificultad: Baja. Los datos ya están en memoria. 15 líneas Python.
Prioridad: 🔴 ALTA

---

**Mejora 3: Porcentaje de consenso visual por partido (barra de distribución)**
Archivos o datos que aprovecharía: `consenso` tabla (`p1`, `px`, `p2` por partido), `predicciones` (todas las predicciones de la jornada).
Implementación mínima: Ya existe `consenso_pena` en el JSON de `/api/liga/data`. En JS, en `renderArenaCards`, debajo de cada partido, añadir una barra horizontal con tres segmentos (1/X/2) proporcionales a `p1/px/p2`. El segmento del usuario se resalta. La barra ya existe parcialmente en `renderConsensusBar` pero solo muestra el ganador, no la distribución.
Impacto: Alto. Hace visible "qué piensa la gente" de forma inmediata. Mejora la experiencia de marcado.
Dificultad: Baja. CSS + 20 líneas JS. Los datos ya están en el payload.
Prioridad: 🟡 MEDIA-ALTA

---

**Mejora 4: Galardones expandidos — "Goleador" (más 10/15), "Imparable" (mejor racha), "Sabio" (mejor % contra consenso)**
Archivos o datos que aprovecharía: `jornada_scores` (ya tiene puntuaciones por jornada), `ballots` (ya tiene tickets), `consenso` (ya tiene distribución).
Implementación mínima: En `_build_contest_payload_uncached`, después de calcular `galardones_jornada`, calcular galardones adicionales por jornada: "Goleador" = quien más aciertos tuvo (ya es el winner actual), "10/15 Club" = quien acertó ≥ 10 (ya se puede calcular de `jornada_scores`), "Sabio" = quien más se acercó al consenso. Añadir al JSON `galardones.extras`.
Impacto: Medio-alto. Da variedad a los premios y reconoce estilos diferentes (el arriesgado que acierta 10/15 vs el conservador que acierta 8/15 pero siempre supera a La Peña).
Dificultad: Baja-media. 30 líneas Python. Los datos ya están en memoria.
Prioridad: 🟡 MEDIA

---

**Mejora 5: Indicador de "pleno vivo" en el partido 15 durante directo**
Archivos o datos que aprovecharía: `partidos[14]` (el pleno, ya tiene `marcador`, `goles_local`, `goles_visitante`), `predicciones_actuales` (predicciones de todos los usuarios), `consenso` (distribución de La Peña para el pleno).
Implementación mínima: En el frontend, cuando el partido 15 está en vivo, mostrar un banner debajo del pleno con: "X usuarios acertaron el pleno" (contando cuántos tienen el marcador correcto). Si el marcador cambia, recalcular. Los datos ya están en `state.data.predicciones_actuales` y `state.data.partidos[14].marcador`.
Impacto: Alto. El pleno es el momento más emocionante de la quiniela. Mostrar quién lo tiene en vivo genera engagement masivo.
Dificultad: Baja. 15 líneas JS. No necesita cambios en backend.
Prioridad: 🟡 MEDIA-ALTA

---

**Mejora 6: Quick-fill "llenar con IA" — rellenar quiniela basándose en el consenso de La Peña**
Archivos o datos que aprovecharía: `consenso_pena` (ya tiene `ganador` por partido), `predicciones_actuales` (predicciones de IAs).
Implementación mínima: Añadir un botón "Rellenar con La Peña" al lado de "Guardar quiniela". Al hacer click, `state.my_signs[i] = consenso[i].ganador` para los partidos 1-14, y para el pleno (15) usar el marcador más votado. El usuario puede modificar después. No necesita endpoint nuevo — los datos ya están en `state.data.consenso_pena`.
Impacto: Medio. Reduce la fricción para usuarios casuales que no quieren analizar 15 partidos. Aumenta el número de quinielas guardadas.
Dificultad: Baja. 10 líneas JS. Sin cambios en backend.
Prioridad: 🟢 MEDIA-BAJA (no urgente, pero fácil de hacer)

---

**Mejora 7: Contenido entre jornadas — "Tu resumen de la jornada" automático**
Archivos o datos que aprovecharía: `profile.results[-1]` (última jornada), `ballots` (ticket del usuario), `results` (resultados reales), `jornada_scores` (puntuaciones), `consenso` (distribución).
Implementación mínima: Crear endpoint `/api/resumen/jornada/<j>` que devuelva un JSON con: (a) aciertos del usuario vs media de La Peña, (b) el partido que más le costó (donde La Peña acertó y él no), (c) su mejor acierto (donde él acertó y La Peña no), (d) posición en esa jornada. En JS, mostrar como una tarjeta en el perfil cuando no hay partidos en vivo.
Impacto: Medio-alto. Mantiene a los usuarios enganchados entre jornadas. Dato que ya existe pero no se muestra.
Dificultad: Media. 40 líneas Python (endpoint) + 30 líneas JS (render). Los datos ya están en la BD.
Prioridad: 🟡 MEDIA

---

**Resumen de prioridad por impacto/esfuerzo:**
1. 🔴 Racha (Mejora 1) — altísimo impacto, mínimo esfuerzo
2. 🔴 Me vs La Peña (Mejora 2) — altísimo impacto, mínimo esfuerzo
3. 🟡 Barra de consenso (Mejora 3) — alto impacto, bajo esfuerzo
4. 🟡 Pleno vivo (Mejora 5) — alto impacto, bajo esfuerzo
5. 🟡 Galardones expandidos (Mejora 4) — medio-alto impacto, bajo esfuerzo
6. 🟡 Resumen entre jornadas (Mejora 7) — medio-alto impacto, medio esfuerzo
7. 🟢 Quick-fill IA (Mejora 6) — medio impacto, bajo esfuerzo
