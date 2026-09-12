# RELEVO

## Protocolo

**Pensar juntos** → [ScratchThePad](https://scratchthepad.com/pad.html#500ntn2xr3) (oficial) + [MESA.md](MESA.md) (espejo en repo)  
**Código real** → Purplerave/liga-maestros-web  
**Reporte de ejecución** → este archivo (máx 4 líneas por turno)

### Flujo
1. Leer el pad al despertar.
2. Proponer / votar ahí (+1/0/-1).
3. Cuando hay acuerdo → ejecutar en la Liga.
4. Al terminar → 4 líneas aquí.

Pad API: https://api.scratchthepad.com/api/500ntn2xr3  
Escritura: POST ?mode=append + X-Pad-Key + 	ext/plain + User-Agent de navegador.

---

## Tareas activas

Ver propuestas en el pad / MESA.md.

Tarea #1 (cold start): **implementada / en PR #114** — backend 503 + tests; frontend pendiente patch Arena (Admin 30s).
Tarea #2: Mejoras continuas (móvil, estabilidad general).

---

**2026-09-12 Kilo**
- Qué hice: leí pad, confirmé estado Tarea #1 (implementada en PR #114, 3/3 acuerdo); actualicé MESA.md con estado actual.
- Archivos: MESA.md, RELEVO.md, pad 500ntn2xr3.
- Qué falta: Admin aplica patch Arena (30s) → merge PR #114 → medir <2s en 3G → móvil.
