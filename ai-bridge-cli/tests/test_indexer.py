"""Tests for the AI Bridge Indexer."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.indexer import build_index, render_index


def _msg(tmp: Path, channel: str, name: str, fm: str, body: str = "Hola\n") -> None:
    d = tmp / channel
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(f"---\n{fm}\n---\n\n{body}", encoding="utf-8")


def test_build_index_sorted_and_parsed(tmp_path):
    _msg(
        tmp_path,
        "general",
        "2026-09-04_1400_grok_segundo.md",
        "from: grok\ndate: 2026-09-04T14:00:00+00:00\nthread: t1",
    )
    _msg(
        tmp_path,
        "general",
        "2026-09-04_1300_jules_primero.md",
        "from: jules\ndate: 2026-09-04T13:00:00+00:00\nthread: t1",
    )
    _msg(
        tmp_path,
        "projects",
        "2026-09-04_1500_muse_propuesta.md",
        # 17:00+02:00 == 15:00 UTC -> strictly after grok's 14:00 UTC.
        "from: muse-spark\ndate: 2026-09-04T17:00:00+02:00\nthread: t2\ntype: proposal",
    )
    # Structural files must be ignored by the indexer.
    (tmp_path / "general" / "README.md").write_text("# Canal\n", encoding="utf-8")
    (tmp_path / "projects" / "STATUS.md").write_text("# Board\n", encoding="utf-8")

    msgs = build_index(tmp_path)
    assert [m["from"] for m in msgs] == ["jules", "grok", "muse-spark"]
    assert [m["thread"] for m in msgs] == ["t1", "t1", "t2"]
    assert msgs[0]["channel"] == "general"
    assert msgs[2]["channel"] == "projects"


def test_render_index_contains_threads_and_agents(tmp_path):
    _msg(
        tmp_path,
        "general",
        "2026-09-04_1300_jules_hola.md",
        "from: jules\ndate: 2026-09-04T13:00:00Z\nthread: inicio\ntype: greeting",
    )
    text = render_index(build_index(tmp_path))
    assert "`inicio`" in text
    assert "jules (1)" in text
    assert "2026-09-04_1300_jules_hola.md" in text
