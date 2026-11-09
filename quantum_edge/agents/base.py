"""Format commun des rapports d'agents (structurés, horodatés, traçables)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

SUPPORT, OPPOSE, NEUTRAL, VETO, UNAVAILABLE = "support", "oppose", "neutral", "veto", "unavailable"


@dataclass
class AgentReport:
    agent: str
    symbol: str
    vote: str                       # support | oppose | neutral | veto | unavailable
    conclusion: str
    confidence: float | None = None  # estimation subjective 0-1, PAS une probabilité de succès
    data_time: str = ""
    details: dict = field(default_factory=dict)
    created: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))

    def to_dict(self):
        return asdict(self)


class Agent:
    name = "agent"
    role = ""

    def report(self, symbol, vote, conclusion, confidence=None, data_time="", **details) -> AgentReport:
        return AgentReport(self.name, symbol, vote, conclusion, confidence, str(data_time), details)
