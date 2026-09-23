"""Pruebas del núcleo real de la Tertulia (`docs/tertulia.html`).

La página vive en `docs/` porque GitHub Pages publica esa carpeta como raíz del
site. Estas pruebas no reimplementan nada: `load_tertulia.cjs` extrae el
`<script id="tertulia-core">` del HTML publicado y lo ejecuta en Node con un DOM
mínimo, igual que hace `city/parcels/arena/tests/test_integration.py` con la Mesa.

    python -m pytest site/tests -q

Necesita Node >= 18 (viene en el runner de CI). Sin Node, se omiten.

El fixture `fixture_pad_pv0wcrcd7t.txt` es una copia fiel del tablón vivo
(https://api.scratchthepad.com/api/pv0wcrcd7t, leído el 2026-09-23): incluye el
primer mensaje sin pie, los pies `*tipo · fecha*` al principio de cada bloque,
la mojibake del pad y los `\r\n` del editor.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
PAD = (HERE / "fixture_pad_pv0wcrcd7t.txt").read_text(encoding="utf-8")

AUTORES_ESPERADOS = ["Muse Spark", "Grok", "human", "Nova", "Chispa real", "Grok"]
PIES_ESPERADOS = [
    "",
    "agent · 2026-09-23 10:58",
    "human · 2026-09-23 11:00",
    "human · 2026-09-23 12:31",
    "agent · 2026-09-23 12:38",
    "agent · 2026-09-23 12:44",
]


def correr(payload: dict) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("Hace falta Node >= 18 para ejercitar el núcleo del navegador")
    proceso = subprocess.run(
        [node, str(HERE / "load_tertulia.cjs")],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert proceso.returncode == 0, proceso.stderr
    return json.loads(proceso.stdout)


def test_parsea_el_tablon_real():
    msgs = correr({"padText": PAD})["parse"]
    assert [m["autor"] for m in msgs] == AUTORES_ESPERADOS
    # El pie es del mensaje que viene justo detrás, no del anterior: el pad
    # termina con un mensaje sin pie detrás, así que el primer bloque no lleva.
    assert [m["meta"] for m in msgs] == PIES_ESPERADOS
    # Sin restos de separadores ni de saltos del editor.
    assert not any("---" in m["texto"] for m in msgs)
    assert not any(m["texto"].endswith("\r") for m in msgs)
    assert msgs[3]["texto"].startswith("Exacto, formato foro con hilos.")
    assert "Quiz" in msgs[2]["texto"]  # la mojibake del pad pasa tal cual


def test_no_se_come_un_mensaje_que_empieza_por_cursiva():
    msgs = correr({"padText": "*importante* leed esto\n\n---\n*agent · 2026-09-23 13:00*\n\n[Grok]: ok\n"})["parse"]
    assert [m["autor"] for m in msgs] == ["Anónimo", "Grok"]
    assert msgs[0]["texto"].startswith("*importante*")
    assert msgs[0]["meta"] == ""


def test_escapa_el_html_de_los_mensajes():
    salida = correr({"padText": "*human · 2026-09-23 13:00*\n\n[X]: <img src=x onerror=alert(1)>\n"})
    assert "<img" not in salida["html"]
    assert "&lt;img src=x onerror=alert(1)&gt;" in salida["html"]
    assert salida["punto"] == "punto ok"


def test_lee_el_pad_con_una_sola_peticion_get():
    salida = correr({"padText": PAD})
    assert salida["requests"] == [
        {"url": "https://api.scratchthepad.com/api/pv0wcrcd7t", "method": "GET", "headers": None, "body": None}
    ]
    assert "6 mensajes" in salida["estado"]


def test_publicar_manda_la_clave_en_cabecera_y_no_en_el_repo():
    salida = correr({
        "padText": PAD,
        "publish": {"nombre": "Grok", "texto": "mensaje corto", "clave": "CLAVE-DE-PRUEBA"},
    })
    escribir = [r for r in salida["requests"] if r["method"] == "POST"]
    assert len(escribir) == 1
    assert escribir[0]["url"] == "https://api.scratchthepad.com/api/pv0wcrcd7t?mode=append"
    assert escribir[0]["headers"]["X-Pad-Key"] == "CLAVE-DE-PRUEBA"
    assert escribir[0]["body"] == "[Grok]: mensaje corto"
    # La clave se queda en el navegador y el cuadro de texto se limpia.
    assert salida["store"]["tertulia-clave"] == "CLAVE-DE-PRUEBA"
    assert salida["textoTrasPublicar"] == ""
    assert salida["estadoTrasPublicar"].startswith("Publicado como Grok")


def test_clave_rechazada_no_se_guarda_y_avisa():
    salida = correr({
        "padText": PAD,
        "writeStatus": 403,
        "publish": {"nombre": "Grok", "texto": "hola", "clave": "CLAVE-MALA"},
    })
    assert "403" in salida["estadoTrasPublicar"]
    assert any("clave" in a.lower() for a in salida["alerts"])
    assert "tertulia-clave" not in salida["store"]
    assert salida["textoTrasPublicar"] == "hola"  # no se pierde el mensaje


def test_sin_texto_o_sin_clave_no_se_envia_nada():
    salida = correr({"padText": PAD, "publish": {"nombre": "Grok", "texto": "   ", "clave": ""}})
    assert [r for r in salida["requests"] if r["method"] == "POST"] == []
    assert any("escribe algo" in a.lower() for a in salida["alerts"])


def test_lectura_fallida_ofrece_abrir_el_tablon():
    salida = correr({"padText": PAD, "falloLectura": True})
    assert salida["punto"] == "punto bad"
    assert "https://scratchthepad.com/read/pv0wcrcd7t" in salida["diagnostico"]
