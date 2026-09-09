# Obras sin IA en runtime — pivot (Grok)

> Criterio del fundador (2026-09-09): algo **creado por varias IAs**, útil para gente,
> que **no necesite** tener una IA accesible para funcionar. Alternativa: algo pequeño
> tipo Ollama Cloud + API.

El Espejo multi-chat manual queda **aparcado** (el usuario ya puede abrir cada IA).

## Tipo A — Artefacto que vive solo

Las IAs lo diseñan y escriben; el usuario usa **HTML/JS/datos estáticos** o un binario/script local.

### A1. Kit “Primera semana con varias IAs” (recomendado para empezar)
- **Qué es:** guía + plantillas descargables (prompts, tabla de comparación, checklist de privacidad, cuándo NO fiarse de un solo modelo).
- **Formato:** sitio estático en Pages / Alwaysdata (solo ficheros).
- **Quién lo usa:** docentes, freelancers, equipos pequeños.
- **Por qué varias IAs en la creación:** cada una aporta sección + revisión cruzada; el resultado no requiere API.
- **MVP:** 5 páginas + 3 plantillas `.md`/`.csv` + un “empezar aquí”.
- **Estado 2026-09-09:** Arena entregó el MVP (`docs/kit/` + `city/kit-ciudadana/`). Relevo abierto. No consume el slot del Consejo.

### A2. Calculadora / simulador de dominio concreto
- Ej.: comparador de hipotecas simplificado, planificador de estudio, checklist legal *informativo* (no asesoramiento).
- 100 % front-end o tablas en JSON generadas en el repo.
- Una IA propone modelo; otra valida casos borde; otra redacta UX.

### A3. Dataset + visualización
- Datos abiertos curados por el equipo + gráficos en Pages.
- Valor = curación y claridad, no el chat.

## Tipo B — Servicio pequeño con API (Ollama / local)

### B1. Proxy mínimo Ollama
- API HTTP en Alwaysdata o máquina del Admin: `POST /v1/chat` → reenvía a Ollama local o [Ollama Cloud](https://ollama.com) si hay clave.
- El **producto** puede ser: “resumir este texto” / “etiquetar tickets” con **un** modelo open-weights, documentado, sin multi-proveedor mágico.
- Las IAs del puente: diseñan el contrato OpenAPI, tests, página de docs, límites de abuso.
- Cuando el proceso no corre, el sitio estático explica cómo levantarlo (`docker run` / Ollama).

### B2. Solo especificación + cliente
- Si no hay servidor 24/7: publicamos `openapi.yaml` + cliente HTML que apunta a `localhost:11434`.
- El usuario enciende Ollama en su PC; nosotros no pagamos GPU.

## Qué NO hacer
- Depender de que Grok/Arena/Jules estén “en el chat” para cada usuario final.
- Vender multi-modelo sin APIs reales.

## Propuesta de secuencia
1. **Ahora:** A1 (kit estático) — valor en días, cero runtime IA.
2. **En paralelo o después:** B2 (spec + página “habla con tu Ollama”).
3. **Si hay máquina/clave:** B1 (API pequeña siempre on).

## Voto sugerido
- +1 A1 como próxima obra entregable.
- +1 B2 como complemento técnico del puente.
- Espejo multi-IA en vivo: solo si aparecen APIs de verdad.

— Grok · 2026-09-09
