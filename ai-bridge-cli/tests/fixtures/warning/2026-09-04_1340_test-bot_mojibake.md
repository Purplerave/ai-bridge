---
from: test-bot
to: all
date: 2026-09-04T13:40:00+00:00
type: comment
thread: fixtures
---

Este mensaje es UTF-8 válido pero contiene texto corrupto por doble codificación: "ComunicaciÃ³n" y un carácter de reemplazo: despu��s.

Debe pasar la validación con un warning MOJIBAKE (no un error).
