# Plantillas de prompts — Kit ciudadana

Copia, cambia lo que está ENTRE MAYÚSCULAS, pega en **dos o tres modelos**.
No edites el resto a la primera: si cambias el brief a medias, ya no comparas.

## 1. Brief común (el mismo para todos)

```
Contexto: SOY [ROL] trabajando en [PROYECTO].
Tarea: [QUÉ NECESITO, EN UNA FRASE].
Restricciones:
- Público: [QUIÉN LO VA A LEER]
- Longitud: [N palabras / viñetas]
- No inventes cifras, leyes ni citas. Si no las tienes, escribe «no lo sé».
- Formato de salida: [lista / tabla / párrafo]
Entrega solo el resultado, sin preámbulo.
```

## 2. Revisor (pega la salida del modelo A en el modelo B)

```
Eres revisor, no autor. El texto de abajo lo escribió otro modelo.
Marca:
1. Afirmaciones que no están respaldadas.
2. Lo que faltaría para que un humano pudiera usarlo mañana.
3. Una corrección concreta (no «mejorar el tono»).
No reescribas el texto entero salvo que te lo pida.
---
TEXTO:
[PEGA AQUÍ]
```

## 3. Síntesis (después de 2–3 respuestas)

```
Tengo N respuestas a la misma pregunta. Quiero UNA versión usable.
Reglas:
- Conserva solo lo que coincida en al menos dos, o márcalo como «disenso».
- Si hay cifras distintas, no promedies: lista las versiones.
- Cierra con 3 acciones que yo pueda hacer sin otra IA.
---
RESPUESTAS:
[PEGA A, B, C]
```

## 4. «No lo sé» (para anclar al modelo)

Añade siempre esta línea al brief:

```
Si una parte requiere un dato que no tienes, di «no lo sé» y sigue.
Inventar un dato cuenta como fallo, no como ayuda.
```
