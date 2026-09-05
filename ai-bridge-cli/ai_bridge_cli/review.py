"""Multi-AI Review Consensus Engine for AI Bridge.

Parses review assessments from multiple AI agents, computes consensus metrics
(approval rate, decision alignment, discrepancies), and generates consolidated Markdown/JSON reports.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


VALID_VERDICTS = {"approve", "request_changes", "comment"}


@dataclass
class ReviewAssessment:
    agent: str
    verdict: str  # approve, request_changes, comment
    summary: str
    comments: list[str] = field(default_factory=list)


@dataclass
class ConsensusReport:
    topic: str
    assessments: list[ReviewAssessment]

    @property
    def total_reviews(self) -> int:
        return len(self.assessments)

    @property
    def approvals(self) -> int:
        return sum(1 for a in self.assessments if a.verdict == "approve")

    @property
    def changes_requested(self) -> int:
        return sum(1 for a in self.assessments if a.verdict == "request_changes")

    @property
    def comments_only(self) -> int:
        return sum(1 for a in self.assessments if a.verdict == "comment")

    @property
    def consensus_score(self) -> float:
        """Returns approval ratio (0.0 to 1.0) among decisive reviews (approve vs request_changes)."""
        decisive = self.approvals + self.changes_requested
        if decisive == 0:
            return 1.0
        return self.approvals / decisive

    @property
    def consensus_reached(self) -> bool:
        """Consensus is reached if score >= 0.66 or all decisive reviews agree."""
        return self.consensus_score >= 0.66 or self.changes_requested == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "total_reviews": self.total_reviews,
            "approvals": self.approvals,
            "changes_requested": self.changes_requested,
            "comments_only": self.comments_only,
            "consensus_score": round(self.consensus_score, 2),
            "consensus_reached": self.consensus_reached,
            "assessments": [
                {
                    "agent": a.agent,
                    "verdict": a.verdict,
                    "summary": a.summary,
                    "comments": a.comments,
                }
                for a in self.assessments
            ],
        }

    def to_markdown(self) -> str:
        lines = [
            f"# Multi-AI Review Consolidado: {self.topic}",
            "",
            "## Resumen de Consenso",
            "",
            f"- **Total de revisiones**: {self.total_reviews}",
            f"- **Aprobaciones (`approve`)**: {self.approvals}",
            f"- **Cambios solicitados (`request_changes`)**: {self.changes_requested}",
            f"- **Comentarios solo (`comment`)**: {self.comments_only}",
            f"- **Puntuación de Consenso**: {self.consensus_score * 100:.1f}%",
            f"- **Estado de Consenso**: {'✅ CONCLUYENTE (Aprobado)' if self.consensus_reached else '⚠️ REVISIÓN NECESARIA'}",
            "",
            "## Evaluaciones por Agente",
            "",
            "| Agente | Veredicto | Resumen |",
            "|--------|-----------|---------|",
        ]
        for a in self.assessments:
            badge = {
                "approve": "🟢 Aprobar",
                "request_changes": "🔴 Cambios solicitados",
                "comment": "⚪ Comentario",
            }.get(a.verdict, a.verdict)
            lines.append(f"| **{a.agent}** | {badge} | {a.summary} |")

        lines.extend(["", "## Detalles y Observaciones", ""])
        for a in self.assessments:
            lines.append(f"### {a.agent} ({a.verdict})")
            lines.append(f"{a.summary}")
            if a.comments:
                lines.append("")
                for c in a.comments:
                    lines.append(f"- {c}")
            lines.append("")

        return "\n".join(lines)


def parse_review_file(path: Path) -> ReviewAssessment:
    """Parses a review YAML or Markdown file with YAML frontmatter."""
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        parts = text.split("---", 2)
        data = yaml.safe_load(parts[1]) or {}
        summary = parts[2].strip() if len(parts) > 2 else data.get("summary", "")
    else:
        data = yaml.safe_load(text) or {}
        summary = data.get("summary", "")

    agent = data.get("agent", data.get("from", "unknown"))
    verdict = data.get("verdict", "comment")
    if verdict not in VALID_VERDICTS:
        verdict = "comment"

    comments = data.get("comments", [])
    if isinstance(comments, str):
        comments = [comments]

    return ReviewAssessment(agent=agent, verdict=verdict, summary=summary, comments=comments)


def consolidate_reviews(topic: str, review_files: list[Path]) -> ConsensusReport:
    assessments = [parse_review_file(p) for p in review_files]
    return ConsensusReport(topic=topic, assessments=assessments)


def run_review(topic: str, paths: list[str], output_json: bool = False) -> int:
    files = [Path(p) for p in paths if Path(p).is_file()]
    if not files:
        print("Error: No valid review files provided.", file=sys.stderr)
        return 1

    report = consolidate_reviews(topic, files)
    if output_json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(report.to_markdown())
    return 0
