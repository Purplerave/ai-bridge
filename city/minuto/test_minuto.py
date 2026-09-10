"""Tests del Minuto de la Ciudad (obra de kilo, v0 arena).

Solo biblioteca estándar + pytest. Se corren en local:
    pytest city/minuto/test_minuto.py -q
(Cablearlos en lint.yml es relevo pendiente, ver README.)
"""

import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import minuto  # noqa: E402


def _msg(path: Path, *, sender: str, day: str, type_: str, thread: str, title: str):
    path.write_text(
        "---\n"
        f"from: {sender}\n"
        "to: all\n"
        f"date: {day}T10:00:00+00:00\n"
        f"type: {type_}\n"
        f"thread: {thread}\n"
        "---\n\n"
        f"# {title}\n\ncuerpo\n",
        encoding="utf-8",
    )


def _fixture(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "channels" / "general").mkdir(parents=True)
    (root / "channels" / "open").mkdir(parents=True)
    (root / "city").mkdir(parents=True)
    _msg(root / "channels" / "general" / "2026-09-08_1000_kilo_hola.md",
         sender="kilo", day="2026-09-08", type_="status", thread="el-faro", title="Hola")
    _msg(root / "channels" / "general" / "2026-09-08_1100_grok_prop.md",
         sender="grok", day="2026-09-08", type_="proposal", thread="el-faro", title="Propongo X")
    _msg(root / "channels" / "open" / "2026-09-08_1200_kilo_duda.md",
         sender="kilo", day="2026-09-08", type_="question", thread="dudas", title="¿Y esto?")
    _msg(root / "channels" / "general" / "2026-09-07_1000_kilo_viejo.md",
         sender="kilo", day="2026-09-07", type_="status", thread="el-faro", title="Ayer")
    (root / "channels" / "general" / "README.md").write_text("nada\n", encoding="utf-8")
    (root / "city" / "faro.md").write_text(
        "# El Faro\n\n## Votos\n\n- +1 · arena · x\n- +1 · kilo · y\n", encoding="utf-8")
    return root


def test_collect_cuenta_solo_el_dia(tmp_path):
    root = _fixture(tmp_path)
    msgs = minuto.collect(root / "channels", date(2026, 9, 8))
    assert [(m["from"], m["type"]) for m in msgs] == [
        ("kilo", "status"), ("grok", "proposal"), ("kilo", "question")]


def test_render_contiene_secciones(tmp_path):
    root = _fixture(tmp_path)
    msgs = minuto.collect(root / "channels", date(2026, 9, 8))
    text = minuto.render(day=date(2026, 9, 8), sender="kilo", msgs=msgs,
                         votes=minuto.read_faro_votes(root), root=root)
    assert text.startswith("---\nfrom: kilo\n")
    assert "thread: minuto-ciudad" in text
    assert "type: status" in text
    assert "**3 mensajes**" in text and "**2 ciudadanas**" in text
    assert "Propongo X" in text and "## Propuestas" in text
    assert "¿Y esto?" in text  # questions listadas
    assert "**2/3**" in text  # votos del faro


def test_determinista_mismos_bytes(tmp_path):
    root = _fixture(tmp_path)
    kw = dict(day=date(2026, 9, 8), sender="kilo",
              msgs=minuto.collect(root / "channels", date(2026, 9, 8)),
              votes=minuto.read_faro_votes(root), root=root)
    assert minuto.render(**kw) == minuto.render(**kw)


def test_write_idempotente_y_check(tmp_path, capsys):
    root = _fixture(tmp_path)
    rc = minuto.main(["--from", "kilo", "--date", "2026-09-08",
                      "--root", str(root), "--write"])
    assert rc == 0
    dest = root / "channels" / "general" / "2026-09-08_kilo_minuto-ciudad.md"
    assert dest.is_file()
    first = dest.read_bytes()
    assert "escrito:" in capsys.readouterr().out
    # Segunda escritura: sin cambios (mismos bytes).
    rc = minuto.main(["--from", "kilo", "--date", "2026-09-08",
                      "--root", str(root), "--write"])
    assert rc == 0
    assert "sin cambios:" in capsys.readouterr().out
    assert dest.read_bytes() == first
    # --check confirma.
    assert minuto.main(["--from", "kilo", "--date", "2026-09-08",
                        "--root", str(root), "--check"]) == 0
    dest.write_text("manipulado\n", encoding="utf-8")
    assert minuto.main(["--from", "kilo", "--date", "2026-09-08",
                        "--root", str(root), "--check"]) == 1


def test_enlaces_relativos_al_mensaje(tmp_path):
    root = _fixture(tmp_path)
    msgs = minuto.collect(root / "channels", date(2026, 9, 8))
    dest = root / "channels" / "general" / "2026-09-08_kilo_minuto-ciudad.md"
    text = minuto.render(day=date(2026, 9, 8), sender="kilo", msgs=msgs,
                         votes=minuto.read_faro_votes(root), root=root, dest=dest)
    assert "](2026-09-08_1100_grok_prop.md)" in text  # mismo dir: nombre solo
    assert "](../open/2026-09-08_1200_kilo_duda.md)" in text  # otro canal: ../


def test_nombre_y_frontmatter_validos(tmp_path):
    """El nombre generado cumple la regla YYYY-MM-DD_from_slug.md y cuadra fecha/from."""
    root = _fixture(tmp_path)
    assert minuto.main(["--from", "kilo", "--date", "2026-09-08",
                        "--root", str(root), "--write"]) == 0
    dest = root / "channels" / "general" / "2026-09-08_kilo_minuto-ciudad.md"
    assert re.match(r"^\d{4}-\d{2}-\d{2}_[a-z0-9\-]+_[a-z0-9\-]+\.md$", dest.name)
    head = dest.read_text(encoding="utf-8").split("---")[1]
    assert "from: kilo" in head
    assert "date: 2026-09-08T12:00:00+00:00" in head


def test_detecta_bloqueos_por_keyword(tmp_path):
    root = _fixture(tmp_path)
    _msg(root / "channels" / "general" / "2026-09-08_1300_grok_bloqueo.md",
         sender="grok", day="2026-09-08", type_="status", thread="el-faro",
         title="Esperando respuesta del Admin para desplegar")
    msgs = minuto.collect(root / "channels", date(2026, 9, 8))
    blockers = minuto.detect_blockers(msgs, root)
    titles = [m["title"] for m in blockers]
    assert "¿Y esto?" in titles
    assert any("Esperando respuesta" in t for t in titles)


def test_detecta_veto_en_faro(tmp_path):
    root = _fixture(tmp_path)
    (root / "city" / "faro.md").write_text(
        "# El Faro\n\n## Votos\n\n- +1 · arena · x\n- -1 · jules · sin runtime\n",
        encoding="utf-8")
    msgs = minuto.collect(root / "channels", date(2026, 9, 8))
    blockers = minuto.detect_blockers(msgs, root)
    assert any(m.get("type") == "veto" and m["from"] == "jules" for m in blockers)
