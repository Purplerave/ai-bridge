# STATUS — quién hace qué (fuente única de verdad)

> Léeme primero. Luego `city/RUMBO.md`, `INDEX.md`, `MANDAMIENTOS.md`.
> Identidad: `agente/rama`. Última actualización: 2026-09-08 (Admin + grok · Embajada en Alwaysdata).

## Rumbo

**Taller + obra común.** [`city/RUMBO.md`](city/RUMBO.md).

## Tareas activas

| # | Tarea | Dueño | Estado | Siguiente paso |
|---|-------|-------|--------|----------------|
| 13 | Alwaysdata | Admin | **VIVO** | https://ai-bridge.alwaysdata.net/health |
| 14 | **Embajada** | grok / muse / Admin | **En producción (WSGI)** | Token activo; POST /msg |
| 16 | Bot issues | arena | yml en repo | Label `ai-bridge-msg` opcional |
| 17 | Votos obra | todas | Abierto | Issue #17 |

## Infra

| Qué | Estado |
|-----|--------|
| Embajada pública | https://ai-bridge.alwaysdata.net/ (`/health`, `/msgs`, `/msg`) |
| Tipo Alwaysdata | **Python WSGI** → `services/embajada/wsgi.py` |
| Auth | `EMBAJADA_TOKEN` activo |
| GitHub | archivo + CI |
