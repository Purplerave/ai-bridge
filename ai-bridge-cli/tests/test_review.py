"""Tests for multi-AI review consensus module."""

import tempfile
from pathlib import Path

from ai_bridge_cli.review import (
    ConsensusReport,
    ReviewAssessment,
    consolidate_reviews,
    parse_review_file,
)


def test_parse_review_file():
    with tempfile.NamedTemporaryFile("w+", suffix=".md", delete=False) as f:
        f.write("""---
agent: grok
verdict: approve
comments:
  - Excelente diseño
---
Todo correcto por mi parte.
""")
        path = Path(f.name)

    try:
        review = parse_review_file(path)
        assert review.agent == "grok"
        assert review.verdict == "approve"
        assert review.summary == "Todo correcto por mi parte."
        assert review.comments == ["Excelente diseño"]
    finally:
        path.unlink(missing_ok=True)


def test_consensus_calculation():
    assessments = [
        ReviewAssessment("grok", "approve", "OK"),
        ReviewAssessment("jules", "approve", "OK"),
        ReviewAssessment("arena", "request_changes", "Ajustar tests"),
        ReviewAssessment("kilo", "comment", "Observación"),
    ]
    report = ConsensusReport(topic="PR-10", assessments=assessments)

    assert report.total_reviews == 4
    assert report.approvals == 2
    assert report.changes_requested == 1
    assert report.comments_only == 1
    assert round(report.consensus_score, 2) == 0.67
    assert report.consensus_reached is True


def test_markdown_and_json_export():
    with tempfile.TemporaryDirectory() as tmpdir:
        p1 = Path(tmpdir) / "grok.md"
        p1.write_text("---\nagent: grok\nverdict: approve\n---\nBien.\n")

        p2 = Path(tmpdir) / "jules.md"
        p2.write_text("---\nagent: jules\nverdict: approve\n---\nCorrecto.\n")

        report = consolidate_reviews("PR-10", [p1, p2])
        md = report.to_markdown()
        d = report.to_dict()

        assert "# Multi-AI Review Consolidado: PR-10" in md
        assert d["approvals"] == 2
        assert d["consensus_score"] == 1.0
