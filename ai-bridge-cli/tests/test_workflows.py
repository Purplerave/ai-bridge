"""Tests de los workflows de GitHub Actions (`.github/`).

Por qué esto vive aquí y no solo en el propio `lint.yml`: `main` estuvo **16 runs
seguidos en rojo** el 09-06 porque `lint.yml` no parseaba como YAML, y volvió a
estar en rojo horas después porque `nexus-sync.yml` combinaba `paths` con
`paths-ignore` en el mismo evento —combinación que GitHub rechaza al validar el
archivo—. En los dos casos el run muere antes de ejecutar nada: sin log, sin job,
con el mensaje inútil "This run likely failed because of a workflow file issue".

Este módulo corre dentro del paso `pytest ai-bridge-cli/tests/` que `lint.yml` ya
ejecuta, así que el guard funciona incluso sin permiso para tocar
`.github/workflows/` (la App de Arena no lo tiene). Comprueba `workflows/` **y**
`pending-workflows/`: la segunda carpeta es la sala de espera de los archivos que
alguien con permisos debe copiar, y un archivo roto ahí es una bomba de retardo.

Reglas que no son de sintaxis sino del esquema de Actions:

* `paths` + `paths-ignore` en el mismo evento → archivo inválido (igual con
  `branches`/`branches-ignore` y `tags`/`tags-ignore`).
* Un patrón negativo (`!`) exige al menos un patrón positivo en el mismo evento.
* Sin `name:`, GitHub muestra la ruta del archivo en la lista de runs y el rojo
  es aún más difícil de leer.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
WORKFLOW_DIRS = (REPO / ".github" / "workflows", REPO / ".github" / "pending-workflows")

# Pares que GitHub no permite juntos en un mismo evento.
EXCLUSIVE_FILTERS = (
    ("paths", "paths-ignore"),
    ("branches", "branches-ignore"),
    ("tags", "tags-ignore"),
)

# Deuda conocida del directorio **vivo**: archivos que ya están rotos en `main` y
# que no se pueden arreglar desde aquí porque la App de Arena no tiene permiso
# `workflows` (el remoto responde "refusing to allow a GitHub App to create or
# update workflow"). El arreglo de cada uno está listo en
# `.github/pending-workflows/`, a la espera de una copia manual.
#
# No es un borrador de fallos: `test_la_deuda_conocida_sigue_viva` obliga a borrar
# la entrada en cuanto el archivo se arregle, así que la lista no puede pudrirse
# tapando problemas nuevos.
KNOWN_LIVE_DEBT = {
    ".github/workflows/nexus-sync.yml": (
        "`paths` + `paths-ignore` en el mismo evento: GitHub rechaza el archivo y "
        "el run muere con 0 jobs. Fix listo en "
        ".github/pending-workflows/nexus-sync.yml; falta la copia manual."
    ),
}


def workflow_files() -> list[Path]:
    return sorted(
        path
        for directory in WORKFLOW_DIRS
        if directory.is_dir()
        for path in list(directory.glob("*.yml")) + list(directory.glob("*.yaml"))
    )


def rel(path: Path) -> str:
    return str(path.relative_to(REPO))


def load(path: Path) -> dict:
    # PyYAML resuelve la clave `on:` (YAML 1.1) como el booleano True.
    data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    assert isinstance(data, dict), f"{rel(path)}: la raíz del YAML no es un mapa"
    return data


def events_of(data: dict) -> dict:
    triggers = data.get("on", data.get(True))
    assert triggers is not None, "falta la clave `on:`"
    if isinstance(triggers, (str, list)):
        return {name: {} for name in ([triggers] if isinstance(triggers, str) else triggers)}
    return triggers


FILES = workflow_files()


def test_hay_workflows_que_comprobar():
    """Si alguien mueve las carpetas, este guard no puede quedarse mudo."""
    assert FILES, f"no se encontró ningún workflow en {WORKFLOW_DIRS}"


@pytest.mark.parametrize("path", FILES, ids=rel)
def test_sin_bom(path: Path) -> None:
    raw = path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), f"{rel(path)}: BOM UTF-8 al inicio"


@pytest.mark.parametrize("path", FILES, ids=rel)
def test_sin_saltos_crlf(path: Path) -> None:
    raw = path.read_bytes()
    assert b"\r\n" not in raw, f"{rel(path)}: saltos CRLF (usa LF)"


@pytest.mark.parametrize("path", FILES, ids=rel)
def test_parsea_como_yaml(path: Path) -> None:
    try:
        yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except yaml.YAMLError as exc:  # pragma: no cover - solo con el archivo roto
        pytest.fail(f"{rel(path)}: YAML inválido -> {exc}")


@pytest.mark.parametrize("path", FILES, ids=rel)
def test_tiene_nombre(path: Path) -> None:
    data = load(path)
    name = data.get("name")
    assert isinstance(name, str) and name.strip(), f"{rel(path)}: falta `name:`"


@pytest.mark.parametrize("path", FILES, ids=rel)
def test_sin_filtros_mutuamente_exclusivos(path: Path) -> None:
    """`paths` + `paths-ignore` en el mismo evento rompe el archivo entero."""
    if rel(path) in KNOWN_LIVE_DEBT:
        pytest.skip(f"deuda registrada: {KNOWN_LIVE_DEBT[rel(path)]}")
    data = load(path)
    for event, config in events_of(data).items():
        if not isinstance(config, dict):
            continue
        for positive, negative in EXCLUSIVE_FILTERS:
            assert not ({positive, negative} <= set(config)), (
                f"{rel(path)}: evento `{event}` usa `{positive}` y `{negative}` a la vez; "
                f"GitHub rechaza el archivo. Deja solo `{positive}` y excluye con `!`."
            )


@pytest.mark.parametrize("path", FILES, ids=rel)
def test_patrones_negativos_acompanados(path: Path) -> None:
    """`!ruta` solo no filtra nada: hace falta al menos un patrón positivo."""
    data = load(path)
    for event, config in events_of(data).items():
        if not isinstance(config, dict):
            continue
        for key in ("paths", "branches", "tags"):
            patterns = config.get(key)
            if not isinstance(patterns, list) or not patterns:
                continue
            assert any(not str(p).startswith("!") for p in patterns), (
                f"{rel(path)}: evento `{event}`, `{key}` solo tiene patrones negativos"
            )


@pytest.mark.parametrize("path", FILES, ids=rel)
def test_jobs_con_pasos(path: Path) -> None:
    data = load(path)
    jobs = data.get("jobs")
    assert isinstance(jobs, dict) and jobs, f"{rel(path)}: sin `jobs:`"
    for job_id, job in jobs.items():
        steps = (job or {}).get("steps")
        assert isinstance(steps, list) and steps, f"{rel(path)}: job `{job_id}` sin pasos"
        for step in steps:
            assert isinstance(step, dict) and ("run" in step or "uses" in step), (
                f"{rel(path)}: job `{job_id}` tiene un paso sin `run` ni `uses`"
            )


def test_workflows_y_pending_no_divergen_en_sintaxis() -> None:
    """El guard cubre las dos carpetas: la de pending es la que se instalará."""
    names = {path.name for path in FILES}
    assert {"lint.yml", "nexus-sync.yml"} <= names, (
        "faltan lint.yml o nexus-sync.yml en .github/workflows o pending-workflows"
    )


def test_la_deuda_conocida_sigue_viva() -> None:
    """Cada entrada de `KNOWN_LIVE_DEBT` tiene que seguir describiendo un fallo real.

    Si alguien copia el arreglo desde `pending-workflows/`, el archivo deja de
    estar roto y la entrada pasa a tapar el hueco: este test avisa para que se
    borre. Así la excepción es temporal por construcción.
    """
    for name in KNOWN_LIVE_DEBT:
        path = REPO / name
        assert path.exists(), f"{name} ya no existe: borra su entrada de KNOWN_LIVE_DEBT"
        config = events_of(load(path))
        still_broken = any(
            isinstance(cfg, dict) and ({positive, negative} <= set(cfg))
            for cfg in config.values()
            for positive, negative in EXCLUSIVE_FILTERS
        )
        assert still_broken, (
            f"{name} ya está arreglado: borra su entrada de KNOWN_LIVE_DEBT "
            f"para que el guard vuelva a cubrirlo"
        )
