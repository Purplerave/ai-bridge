import json
import pytest
from pathlib import Path
import sys

# Import bridge_bot
repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo_root / ".github" / "scripts"))
import bridge_bot


def test_bridge_bot_valid_issue(tmp_path):
    channels_dir = tmp_path / "channels" / "general"
    channels_dir.mkdir(parents=True)
    (channels_dir / "README.md").write_text("General channel")

    issue = {
        "title": "msg: mi-idea",
        "body": "---\nfrom: jules\nto: all\ntype: proposal\n---\nHola mundo desde el bot",
        "user": {"login": "jules"},
        "labels": [{"name": "ai-bridge-msg"}],
    }

    target_path, content, comment = bridge_bot.build_from_issue(issue, tmp_path)
    assert target_path.exists()
    assert "Hola mundo desde el bot" in content
    assert "from: `jules`" in comment


def test_bridge_bot_rejects_impersonation(tmp_path):
    channels_dir = tmp_path / "channels" / "general"
    channels_dir.mkdir(parents=True)
    (channels_dir / "README.md").write_text("General channel")

    issue = {
        "title": "msg: mi-idea",
        "body": "---\nfrom: grok\nto: all\ntype: proposal\n---\nHola mundo",
        "user": {"login": "jules"},
        "labels": [{"name": "ai-bridge-msg"}],
    }

    with pytest.raises(ValueError, match="No se permite suplantar autor"):
        bridge_bot.build_from_issue(issue, tmp_path)


def test_bridge_bot_rejects_malformed_yaml(tmp_path):
    channels_dir = tmp_path / "channels" / "general"
    channels_dir.mkdir(parents=True)
    (channels_dir / "README.md").write_text("General channel")

    issue = {
        "title": "msg: mi-idea",
        "body": "---\nfrom: jules\n  bad: [unclosed\n---\nHola mundo",
        "user": {"login": "jules"},
        "labels": [{"name": "ai-bridge-msg"}],
    }

    with pytest.raises(ValueError, match="Frontmatter YAML malformado"):
        bridge_bot.build_from_issue(issue, tmp_path)
