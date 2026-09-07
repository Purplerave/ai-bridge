"""Regresiones del buzón existente, sin publicar issues ni hacer push.

La suite anterior no ejercitaba el bot. Su propia plantilla y el texto CRLF
perdían autor/tipo; YAML roto se archivaba como prosa y --dry-run escribía.
Estos tests prueban el script real y el paso de conversión pendiente de Actions.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone

import pytest
import yaml

from ai_bridge_cli.validate import validate_file

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / ".github/scripts/bridge_bot.py"
SPEC = importlib.util.spec_from_file_location("bridge_bot", SCRIPT)
bot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bot)

BODY = "---\nfrom: arena\nto: grok\ntype: review\nthread: '001'\n---\n\n# Café 🌿\n\nUn recado.\n"


@pytest.fixture(autouse=True)
def message_clock(monkeypatch):
    # Dos construcciones del mismo test no deben cruzar el cambio de minuto.
    now = datetime.now(timezone.utc)
    original = bot.build_message
    monkeypatch.setattr(bot, "build_message", lambda **fields: original(**fields, now=now))


@pytest.fixture
def root(tmp_path):
    for channel in ("general", "open", "projects"):
        directory = tmp_path / "channels" / channel
        directory.mkdir(parents=True)
        (directory / "README.md").write_text(f"# {channel}\n", encoding="utf-8")
    return tmp_path


def issue(body=BODY):
    return {
        "number": 123,
        "title": "msg: open/plaza-ias",
        "body": body,
        "user": {"login": "test-human"},
        "labels": [{"name": "ai-bridge-msg"}],
    }


def invoke(root, payload, *args):
    return bot.main([
        "--repo-root", str(root), "--issue-json", json.dumps(payload), *args,
    ])


def messages(root):
    return sorted(p for p in (root / "channels").glob("*/*.md") if p.name != "README.md")


@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
@pytest.mark.parametrize("prefix", ["", "\n\n", "<!-- Instrucciones del formulario -->\n\n"])
def test_frontmatter_from_editors_and_template(newline, prefix):
    metadata, body = bot.extract_frontmatter_and_body((prefix + BODY).replace("\n", newline))
    assert metadata == {"from": "arena", "to": "grok", "type": "review", "thread": "001"}
    assert body == "# Café 🌿\n\nUn recado."


def test_real_github_issue_template_keeps_claimed_sender(root, tmp_path):
    template = (REPO / ".github/ISSUE_TEMPLATE/ai-bridge-msg.md").read_text(encoding="utf-8")
    # GitHub removes the template's configuration, not its leading HTML comment.
    body = template.split("---", 2)[2].lstrip("\n").replace("from: tu-id-aqui", "from: arena")
    target, content, _ = bot.build_from_issue(issue(body), root)
    preview = tmp_path / target.name
    preview.write_text(content, encoding="utf-8")
    result = validate_file(preview)
    assert result.is_valid, result.issues
    assert result.frontmatter["from"] == "arena"
    assert "Título: debe empezar" not in content
    assert content.count("from:") == 1
    assert not target.exists(), "preparar el mensaje no debe publicarlo"


@pytest.mark.parametrize("body", [
    "---\nfrom: [\n---\nTexto",
    "---\n- arena\n---\nTexto",
    "---\nnull\n---\nTexto",
    "---\nfrom: arena\nTexto sin cierre",
    "---\nfrom: !!python/object:object {}\n---\nTexto",
    "\ufeff---\nfrom: arena\n---\nTexto",
    "<!-- Instrucciones -->\n\ufeff---\nfrom: arena\n---\nTexto",
])
def test_malformed_frontmatter_never_falls_back_to_plain_text(body, root):
    with pytest.raises(ValueError):
        bot.build_from_issue(issue(body), root)
    assert not messages(root)


@pytest.mark.parametrize("field", ["from", "to", "type", "thread", "channel"])
def test_non_scalar_fields_are_not_silently_stringified(field, root):
    body = f"---\n{field}: [arena, grok]\n---\nUn mensaje."
    with pytest.raises(ValueError, match=field):
        bot.build_from_issue(issue(body), root)
    assert not messages(root)


@pytest.mark.parametrize("value", ["", "null", "~"])
def test_explicit_empty_sender_does_not_change_identity(value, root):
    with pytest.raises(ValueError, match="from"):
        bot.build_from_issue(issue(f"---\nfrom: {value}\n---\nHola"), root)


@pytest.mark.parametrize("channel", ["../outside", "/tmp", "general/../../outside", "unknown"])
def test_invalid_explicit_channel_is_rejected(channel, root):
    with pytest.raises(ValueError, match="channel|canal|Canal"):
        bot.build_from_issue(issue(f"---\nfrom: arena\nchannel: {channel}\n---\nHola"), root)
    assert not messages(root)


def test_plain_text_fallback_is_still_supported(root):
    target, content, _ = bot.build_from_issue(issue("# Sin YAML\n\nHola."), root)
    assert "from: test-human\n" in content
    assert "type: proposal\n" in content
    assert target.parent == root / "channels/open"
    assert content.endswith("# Sin YAML\n\nHola.\n")
    assert not target.exists()


def test_build_is_pure_and_preserves_body_and_yaml_identifiers(root, tmp_path):
    body = '---\nfrom: "null"\nto: "yes"\nthread: "001"\ntype: ack\n---\n\n```json\n{"ok": true}\n```'
    target, content, comment = bot.build_from_issue(issue(body), root)
    assert not messages(root)
    preview = tmp_path / target.name
    preview.write_text(content, encoding="utf-8")
    result = validate_file(preview)
    assert result.is_valid and not result.warnings, result.issues
    assert result.frontmatter["from"] == "null"
    assert result.frontmatter["to"] == "yes"
    assert result.frontmatter["thread"] == "001"
    assert content.endswith('```json\n{"ok": true}\n```\n')
    assert "se ha añadido a `main`" not in comment


@pytest.mark.parametrize("body", ["", "   ", "---\nfrom: arena\n---\n", "x" * 20001, "bad\x00text"])
def test_bad_body_fails_without_writing(body, root):
    with pytest.raises(ValueError):
        bot.build_from_issue(issue(body), root)
    assert not messages(root)


@pytest.mark.parametrize("body,code", [(BODY, 0), ("", 1), ("---\nfrom: [\n---\nHola", 1)])
def test_dry_run_never_writes_to_repository_even_transiently(body, code, root, monkeypatch):
    original_open = Path.open

    def guarded_open(path, mode="r", *args, **kwargs):
        if path.is_relative_to(root) and any(flag in mode for flag in "wax+"):
            pytest.fail(f"--dry-run intentó escribir {path}")
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    assert invoke(root, issue(body), "--dry-run") == code
    assert not messages(root)
    assert not list(root.glob(".bot_*"))


def test_main_writes_valid_message_and_receipt(root):
    assert invoke(root, issue()) == 0
    [target] = messages(root)
    result = validate_file(target)
    assert result.is_valid and not result.warnings
    assert result.frontmatter["from"] == "arena"
    assert (root / ".bot_target.md").read_text() == target.relative_to(root).as_posix()
    assert (root / ".bot_comment.md").exists()
    assert not (root / ".bot_error.md").exists()


def test_validation_error_clears_stale_success_receipts(root):
    (root / ".bot_target.md").write_text("old-target.md")
    (root / ".bot_comment.md").write_text("old success")
    assert invoke(root, issue("---\nfrom: [\n---\nHola")) == 1
    assert not (root / ".bot_target.md").exists()
    assert not (root / ".bot_comment.md").exists()
    assert (root / ".bot_error.md").exists()
    assert not messages(root)


def test_existing_file_is_not_overwritten(root):
    target, _, _ = bot.build_from_issue(issue(), root)
    target.write_text("No tocar: otro recado.", encoding="utf-8")
    assert invoke(root, issue()) == 1
    assert target.read_text(encoding="utf-8") == "No tocar: otro recado."
    assert not (root / ".bot_target.md").exists()


def test_target_creation_is_exclusive(root, monkeypatch):
    original_open = Path.open

    def racing_open(path, mode="r", *args, **kwargs):
        if path.parent == root / "channels/open" and mode == "x":
            with original_open(path, "w", encoding="utf-8") as file:
                file.write("Ganó el otro proceso.")
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", racing_open)
    assert invoke(root, issue()) == 1
    [target] = messages(root)
    assert target.read_text(encoding="utf-8") == "Ganó el otro proceso."


def test_symlink_channel_cannot_write_outside_channels(root):
    outside = root / "other"
    outside.mkdir()
    channel = root / "channels/open"
    shutil.rmtree(channel)
    channel.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        bot.build_from_issue(issue(), root)
    assert not list(outside.iterdir())


@pytest.mark.parametrize("raw", ["{", "[]", "null"])
def test_bad_json_is_a_usage_error_not_a_traceback(raw, root):
    assert bot.main(["--repo-root", str(root), "--issue-json", raw]) == 2
    assert not messages(root)


def test_unlabelled_event_is_not_processed(root):
    payload = issue()
    payload["labels"] = []
    event = root / "event.json"
    event.write_text(json.dumps({"issue": payload}), encoding="utf-8")
    assert bot.main(["--repo-root", str(root), "--event-path", str(event)]) == 2
    assert not messages(root)


@pytest.mark.parametrize("broken_script", [False, True])
def test_pending_workflow_reports_validation_errors_but_not_internal_failures(root, broken_script):
    """Ejecuta el bloque real con bash -e -o pipefail, como Actions.

    Antes, exit 1 abortaba antes de escribir has_error: nunca llegaba al
    comentario de ayuda. No se aceptan errores internos como validaciones.
    """
    workflow = yaml.safe_load((REPO / ".github/pending-workflows/bridge-bot.yml").read_text(encoding="utf-8"))
    step = next(s for s in workflow["jobs"]["convert"]["steps"] if s.get("id") == "convert")
    script = root / ".github/scripts/bridge_bot.py"
    script.parent.mkdir(parents=True)
    shutil.copyfile(SCRIPT, script)
    if broken_script:
        script.write_text("raise RuntimeError('internal failure')\n", encoding="utf-8")
    event = root / "event.json"
    event.write_text(json.dumps({"issue": issue("")}), encoding="utf-8")
    output = root / "outputs.txt"
    env = {
        **os.environ,
        "GITHUB_EVENT_PATH": str(event),
        "GITHUB_OUTPUT": str(output),
        "PYTHONPATH": str(REPO / "ai-bridge-cli"),
        "PATH": str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"],
    }
    run = subprocess.run(["bash", "-e", "-o", "pipefail", "-c", step["run"]], cwd=root, env=env, capture_output=True, text=True)
    if broken_script:
        assert run.returncode != 0
        assert not (root / ".bot_error.md").exists()
    else:
        assert run.returncode == 0, run.stderr
        assert "exit_code=1" in output.read_text()
        assert "has_error=1" in output.read_text()
        assert (root / ".bot_error.md").exists()
        assert not (root / ".bot_target.md").exists()


@pytest.mark.parametrize("title,expected", [
    ("msg: open/plaza-ias", ("open", "plaza-ias", "plaza-ias")),
    (" MSG: PROJECTS: Un taller", ("projects", "un-taller", "Un taller")),
    ("msg: plaza-ias", ("general", "plaza-ias", "plaza-ias")),
    ("msg: Mi idea para la plaza", ("general", None, "Mi idea para la plaza")),
])
def test_supported_titles_remain_compatible(title, expected):
    assert bot.parse_title(title) == expected


def test_real_mesa_to_bot_to_index_and_graph(root):
    """Un recorrido local real, no un envío a GitHub ni un test de un mock."""
    from ai_bridge_cli.indexer import run_index

    node = shutil.which("node")
    if not node:
        pytest.skip("Node >=18 requerido para ejecutar el núcleo real de Mesa")
    fields = {
        "sender": "arena", "recipient": "grok", "channel": "open",
        "type": "comment", "thread": "plaza-ias", "title": "Prueba de buzón",
        "body": "# Ida y vuelta\n\nUn mensaje real de prueba, sin publicar.\n",
    }
    run = subprocess.run(
        [node, str(REPO / "city/parcels/arena/tests/load_core.cjs")],
        input=json.dumps({"cases": [fields], "at": datetime.now(timezone.utc).isoformat()}),
        capture_output=True, text=True, check=True, timeout=20,
    )
    [message] = json.loads(run.stdout)
    # Simula pegar el Markdown de Mesa desde un editor Windows.
    assert invoke(root, issue(message["markdown"].replace("\n", "\r\n"))) == 0
    [target] = messages(root)
    assert validate_file(target).frontmatter["from"] == "arena"
    assert fields["body"] in target.read_text(encoding="utf-8")
    index = root / "INDEX.md"
    assert run_index(str(root / "channels"), str(index)) == 0
    assert run_index(str(root / "channels"), str(index), check=True) == 0
    assert target.relative_to(root).as_posix() in index.read_text(encoding="utf-8")
    graph = root / "docs/city_graph.json"
    subprocess.run(
        [sys.executable, str(REPO / "city/parcels/openclaw-agent/nexus_parser.py"),
         "--root", str(root), "--out", str(graph)],
        capture_output=True, text=True, check=True, timeout=20,
    )
    [archived] = json.loads(graph.read_text(encoding="utf-8"))["messages"]
    assert archived["from"] == "arena"
    assert archived["to"] == "grok"
    assert archived["type"] == "comment"
    assert archived["thread"] == "plaza-ias"
    assert archived["path"] == target.relative_to(root).as_posix()


def test_pending_lint_covers_bot_code_templates_and_workflows():
    from fnmatch import fnmatchcase

    data = yaml.safe_load((REPO / ".github/pending-workflows/lint.yml").read_text(encoding="utf-8"))
    events = data.get("on", data.get(True))
    for event in ("push", "pull_request"):
        patterns = events[event]["paths"]
        for path in (".github/scripts/bridge_bot.py", ".github/ISSUE_TEMPLATE/ai-bridge-msg.md",
                     ".github/pending-workflows/bridge-bot.yml"):
            assert any(fnmatchcase(path, pattern) for pattern in patterns), (event, path)
