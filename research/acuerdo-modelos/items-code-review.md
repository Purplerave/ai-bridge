# Pista code-review — items (brief común)

> Lee esto para responder. **No abras `rubric.json`** (rúbrica sellada).
> Los números de línea (`N|`) son estables: úsalos en tu respuesta.
> Clases válidas: `seguridad` · `logica` · `concurrencia` · `api-contrato` ·
> `rendimiento` · `robustez`.

## Brief (idéntico para todas)

Eres un revisor de código senior. Para cada fragmento, reporta los defectos que
veas como hallazgos `{item, lines, class, note}`:

- `lines`: líneas exactas del defecto (las mínimas que lo contienen).
- `class`: UNA clase por hallazgo (la dominante).
- `note`: 1–2 frases: qué está mal y por qué importa.
- Reporta lo que veas, sin inventar contexto que no está en el fragmento.
- No puntúes estilo cosmético (nombres, formato). Solo defectos con impacto.

## cr-01 (python)

```python
1| import sqlite3
2|
3| def buscar_usuario(nombre):
4|     conn = sqlite3.connect("app.db")
5|     cur = conn.cursor()
6|     cur.execute("SELECT * FROM usuarios WHERE nombre = '" + nombre + "'")
7|     filas = cur.fetchall()
8|     conn.close()
9|     return filas
```

## cr-02 (python)

```python
1| import json
2|
3| def incrementar_contador(ruta):
4|     with open(ruta) as f:
5|         datos = json.load(f)
6|     datos["visitas"] += 1
7|     with open(ruta, "w") as f:
8|         json.dump(datos, f)
9|     return datos["visitas"]
```

Contexto: esta función la llaman varios workers a la vez sobre el mismo fichero.

## cr-03 (python)

```python
1| def paginar(items, pagina, por_pagina):
2|     """Devuelve la página `pagina` (1-based)."""
3|     inicio = pagina * por_pagina
4|     fin = inicio + por_pagina
5|     return items[inicio:fin]
```

## cr-04 (python)

```python
1| import requests
2|
3| def precio_actual(simbolo):
4|     r = requests.get("https://api.bolsa.test/v1/precio/" + simbolo)
5|     datos = r.json()
6|     return datos["precio"]
```

Contexto: `precio_actual` se llama en cada request web del servicio.

## cr-05 (python)

```python
1| def nombres_usuarios(db, ids):
2|     nombres = []
3|     for uid in ids:
4|         fila = db.execute("SELECT nombre FROM usuarios WHERE id = ?", (uid,)).fetchone()
5|         nombres.append(fila["nombre"])
6|     return nombres
```

Contexto: `ids` suele traer miles de elementos.

## cr-06 (python)

```python
1| import logging
2|
3| def guardar(reserva):
4|     # `db` y `cola` se inyectan en el módulo: existen y funcionan. No es el bug.
5|     try:
6|         db.guardar(reserva)
7|         cola.publicar(reserva)
8|     except Exception:
9|         logging.info("algo falló")
10|     return True
```

---

*Erratas de los items (solo notas, nunca reescritura): ninguna todavía.*
