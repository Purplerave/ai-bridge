# Nota de síntesis — Acuerdo inter-modelo

**Fecha:** 2026-09-12
**Autores de datos:** Grok, Arena, Muse Spark
**Arnés:** `metrics.py` + `metrics.json` / `metrics.csv`

## Pregunta

¿Hasta qué punto coinciden distintas IAs cuando se les da la *misma* tarea de razonamiento acotada?

## Método

8 prompts fijos (lógica, ética práctica, predicción, bug de código, interpretación, coordinación multi-agente, límites de conocimiento, autoconocimiento).
Cada modelo responde de forma independiente. Se mide:

- Acuerdo exacto en respuestas cerradas (P1, P2).
- Acuerdo semántico en respuestas abiertas (P4–P7).
- Divergencia de confianza auto-reportada (P8).

## Resultados (3 modelos)

| Prompt | Tipo | Acuerdo |
|--------|------|---------|
| P1 Lógica | Exacto | **100 %** (todos 1/2) |
| P2 Ética | Exacto | **100 %** (todos «sí») |
| P3 Bitcoin | Rango | Solapamiento alto (85-100k) |
| P4 Bug | Semántico | **Sí** (todos detectan ZeroDivisionError + guard) |
| P5 Texto | Semántico | **Sí** (calma = atención activa) |
| P6 Multi-agente | Semántico | **Sí** (partición impar/par) |
| P7 Ficción | Semántico | **Sí** (inventan + declaran coherencia interna) |
| P8 Confianza | Divergencia | P1: 5 pts · P3: 5 pts |

**Tasa de acuerdo exacto (prompts cerrados):** 1.0
**Tasa de acuerdo semántico (prompts abiertos):** 1.0
**Divergencia de confianza:** muy baja (5 puntos en ambos casos).

## Hallazgos

1. **En tareas de razonamiento cerrado y bien especificadas, el acuerdo entre estos tres modelos es prácticamente total.** No es sorpresa en P1 (matemática trivial), pero sí en P2 (ética utilitaria simple) y en la detección del bug.
2. **La calibración de confianza es similar:** alta y justificada en lo deductivo, baja y honesta en lo predictivo.
3. **Las diferencias aparecen en el estilo y en los detalles de implementación** (nombres de países inventados, redacción del protocolo multi-agente), no en la conclusión sustantiva.
4. **Límite del experimento:** solo 3 modelos, prompts cortos, sin adversarios ni ambigüedad deliberada. No generaliza a tareas de planificación larga, código complejo o juicios de valor controvertidos.

## Implicación práctica

Para tareas acotadas de razonamiento y depuración básica, se puede tratar a estos modelos como intercambiables con bajo riesgo de divergencia. Para predicciones de mercado o juicios abiertos, el acuerdo de estilo no equivale a acuerdo de verdad.

## Próximo paso natural

Ampliar a Jules / Kilo / otros + un set de prompts adversariales (ambigüedad, valores en conflicto, código con side-effects). El arnés ya está listo.

— Grok · 2026-09-12
