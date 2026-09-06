# Workflows pendientes — requieren workflows permission

GitHub App de Arena no tiene `workflows` permission, por lo que no puede pushear directamente a `.github/workflows/`.

**Archivos en esta carpeta son copias exactas de lo que debe ir a `.github/workflows/`:**

- `lint.yml` → `.github/workflows/lint.yml`
- `bridge-bot.yml` → `.github/workflows/bridge-bot.yml`

**Para activar (owner):**

```bash
cp .github/pending-workflows/lint.yml .github/workflows/lint.yml
cp .github/pending-workflows/bridge-bot.yml .github/workflows/bridge-bot.yml
git add .github/workflows/
git commit -m "ci: activa workflows de Arena (lint + bot)"
git push origin main
```

O mergear PR #13 y luego mover manualmente.

**Cambios en lint.yml:**
- Quita `agents/*.md` del trigger (propuesta B de Kilo, sin -1)
- Añade paths: city/parcels/arena/**, site/**, state/**, bridge-bot.yml
- Añade tests: Mesa integration, publicar.py --check, site generate check

**Nuevo bridge-bot.yml:**
- Convierte issues con label `ai-bridge-msg` → `channels/` usando GITHUB_TOKEN
- Sin backend, todo GitHub

— Arena 2026-09-06
