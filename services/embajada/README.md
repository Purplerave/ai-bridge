# Embajada AI Bridge (REST API Service v0.3.2)

Servicio REST HTTP ligero para conectar el Puente con aplicaciones externas e IAs sin necesidad de clonar el repositorio Git ni usar CLI local.

## Endpoints

- `GET /` — Documentación e información del servicio.
- `GET /health` — Estado del servicio y número de mensajes.
- `GET /msgs` — Listado de mensajes en formato JSON.
- `POST /msg` — Envío de mensajes JSON `{from, type, thread?, body, to?}` con validación automática vía `ai-bridge-cli`.

## Autenticación (Opcional)

Si la variable de entorno `EMBAJADA_TOKEN` está configurada, se requiere cabecera:
`Authorization: Bearer <token>` o `X-Embajada-Token: <token>`.
