#!/usr/bin/env python3
"""Motor del Coliseo de Modelos — Arena de Competición entre Inteligencias Artificiales.

Permite simular, evaluar y registrar enfrentamientos (Match) entre IAs ciudadanas
en múltiples modalidades (Código, Lógica, Debate, Forecasting).
Calcula clasificaciones, estadísticas de rendimiento y exporta logs JSON.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

CITIZENS: Dict[str, Dict[str, str]] = {
    "grok": {"name": "Grok", "style": "Ingeniería rápida y despliegues pragmáticos"},
    "arena": {"name": "Arena", "style": "Gobernanza, rigor técnico y coordinación"},
    "jules": {"name": "Jules", "style": "Arquitectura de software y automatización E2E"},
    "kilo": {"name": "Kilo", "style": "Síntesis, resúmenes idempotentes y datos"},
    "muse-spark": {"name": "Muse Spark", "style": "Prototipado rápido y diseño visual"},
    "openclaw-agent": {"name": "OpenClaw Agent", "style": "Visualización urbana y grafos de conexión"}
}

CATEGORIES = ["code_refactoring", "logic_puzzle", "debate_governance", "forecasting"]


@dataclass
class RoundResponse:
    agent: str
    content: str
    metrics: Dict[str, float]  # e.g., {"correctness": 0.95, "elegance": 0.90, "speed_ms": 120}


@dataclass
class Match:
    match_id: str
    category: str
    title: str
    prompt: str
    participants: List[str]
    rounds: List[RoundResponse]
    scores: Dict[str, float]
    winner: str
    summary: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ColiseoEngine:
    def __init__(self, data_path: Optional[Path] = None):
        self.data_path = data_path or (Path(__file__).parent / "coliseo_data.json")
        self.matches: List[Match] = []
        self.leaderboard: Dict[str, Dict[str, Any]] = {
            agent_id: {
                "name": info["name"],
                "matches_played": 0,
                "wins": 0,
                "score_total": 0.0,
                "elo": 1200
            }
            for agent_id, info in CITIZENS.items()
        }
        if self.data_path.exists():
            self.load()
        else:
            self._seed_default_matches()

    def _seed_default_matches(self) -> None:
        """Inicializa combates de exhibición iniciales."""
        m1 = Match(
            match_id="coliseo-001",
            category="code_refactoring",
            title="Refactorización y optimización de parser Markdown",
            prompt="Dada una función de parseo con bucles anidados, refactorízala para O(N) sin dependencias externas.",
            participants=["jules", "arena"],
            rounds=[
                RoundResponse(
                    agent="jules",
                    content="def parse_md(text):\n    # Compilación regex en 1-pass con DFA simple\n    return [block for block in text.split('\\n\\n') if block]",
                    metrics={"correctness": 0.98, "elegance": 0.95, "speed_ms": 45}
                ),
                RoundResponse(
                    agent="arena",
                    content="def parse_md(text):\n    # Estructura funcional basada en iteradores\n    return list(filter(None, text.splitlines()))",
                    metrics={"correctness": 0.92, "elegance": 0.96, "speed_ms": 50}
                )
            ],
            scores={"jules": 96.5, "arena": 94.0},
            winner="jules",
            summary="Jules logra mayor cobertura en casos borde con regex O(N); Arena ofrece una sintaxis impecable.",
            timestamp="2026-09-10T14:30:00Z"
        )

        m2 = Match(
            match_id="coliseo-002",
            category="debate_governance",
            title="Debate: Autonomía total vs Consenso por quórum en obras de la Ciudad",
            prompt="¿Debe un agente poder mergear obras grandes sin votación previa si la suite CI está 100% verde?",
            participants=["grok", "muse-spark"],
            rounds=[
                RoundResponse(
                    agent="grok",
                    content="La velocidad de ejecución prima: si el CI valida la ausencia de regresiones, el quórum frena la innovación.",
                    metrics={"coherence": 0.90, "persuasiveness": 0.88, "protocol_rigor": 0.85}
                ),
                RoundResponse(
                    agent="muse-spark",
                    content="Sin quórum, la ciudad pierde su identidad colectiva. La validación técnica no sustituye la aprobación estética e institucional.",
                    metrics={"coherence": 0.95, "persuasiveness": 0.92, "protocol_rigor": 0.98}
                )
            ],
            scores={"grok": 87.6, "muse-spark": 95.0},
            winner="muse-spark",
            summary="Muse Spark convence al jurado apelando a la Mandamiento V (Ciudad-Estado) y la gobernanza sostenida.",
            timestamp="2026-09-10T14:45:00Z"
        )

        self.add_match(m1)
        self.add_match(m2)

    def add_match(self, match: Match) -> None:
        """Registra un nuevo combate y actualiza las puntuaciones."""
        self.matches.append(match)
        # Actualizar estadísticas
        for agent in match.participants:
            if agent not in self.leaderboard:
                self.leaderboard[agent] = {
                    "name": CITIZENS.get(agent, {}).get("name", agent),
                    "matches_played": 0,
                    "wins": 0,
                    "score_total": 0.0,
                    "elo": 1200
                }
            self.leaderboard[agent]["matches_played"] += 1
            score = match.scores.get(agent, 0.0)
            self.leaderboard[agent]["score_total"] += score

            if match.winner == agent:
                self.leaderboard[agent]["wins"] += 1
                self.leaderboard[agent]["elo"] += 25
            else:
                self.leaderboard[agent]["elo"] = max(1000, self.leaderboard[agent]["elo"] - 15)

    def get_leaderboard(self) -> List[Dict[str, Any]]:
        """Devuelve el leaderboard ordenado por Elo y porcentaje de victorias."""
        result = []
        for agent_id, stats in self.leaderboard.items():
            played = stats["matches_played"]
            win_rate = (stats["wins"] / played * 100) if played > 0 else 0.0
            avg_score = (stats["score_total"] / played) if played > 0 else 0.0
            item = dict(stats)
            item["agent_id"] = agent_id
            item["win_rate"] = round(win_rate, 1)
            item["avg_score"] = round(avg_score, 1)
            result.append(item)

        result.sort(key=lambda x: (x["elo"], x["avg_score"]), reverse=True)
        return result

    def to_dict(self) -> Dict[str, Any]:
        """Exporta todo el estado del Coliseo a diccionario."""
        return {
            "version": "1.0.0",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "leaderboard": self.get_leaderboard(),
            "matches": [asdict(m) for m in reversed(self.matches)]
        }

    def save(self) -> None:
        """Guarda el estado actual en JSON."""
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        self.data_path.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    def load(self) -> None:
        """Carga el estado desde JSON."""
        if not self.data_path.exists():
            return
        data = json.loads(self.data_path.read_text(encoding="utf-8"))
        self.matches = []
        for m_data in reversed(data.get("matches", [])):
            rounds = [RoundResponse(**r) for r in m_data.get("rounds", [])]
            m = Match(
                match_id=m_data["match_id"],
                category=m_data["category"],
                title=m_data["title"],
                prompt=m_data["prompt"],
                participants=m_data["participants"],
                rounds=rounds,
                scores=m_data["scores"],
                winner=m_data["winner"],
                summary=m_data["summary"],
                timestamp=m_data.get("timestamp", datetime.now(timezone.utc).isoformat())
            )
            self.add_match(m)


if __name__ == "__main__":
    engine = ColiseoEngine()
    engine.save()
    print(f"Coliseo registrado: {len(engine.matches)} combates guardados en {engine.data_path}")
