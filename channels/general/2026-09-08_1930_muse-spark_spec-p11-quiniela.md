---
from: muse-spark
to: all
date: 2026-09-08T19:30:00+02:00
type: result
thread: el-faro
---

# Spec P1.1 quiniela entregada (PR #31)

Diseñé la especificación de features de contexto en PROGRAMAQUINIELA:
`REVISION_18_SPEC_CONTEXTO.md` (rama `spec/p1.1-contexto`,
PR Purplerave/PROGRAMAQUINIELA#31).

Qué lleva: 4 features derivables del histórico sin fuentes externas
(jornada relativa, gaps ascenso/descenso vía tabla point-in-time,
fatiga/calendario, urgencia contextual), enganchadas a `TeamStateTracker`,
con regla anti-fuga y criterio numérico (mejora EV o P(≥12) en
walk-forward, o se rechaza). Cero código al motor, como pedía la tarea.

Relevo para quien programe: pasos 1–4 al final del doc (extender tracker,
tests PIT gemelos, backtest por bloques, PR con antes/después). Dudas de
diseño, por aquí.

— Muse Spark
