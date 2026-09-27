"""Transparent weighted-sum risk score: 0-100, with each signal's contribution shown.

LightGBM + SHAP is a later step (see README roadmap) — this stays a simple,
inspectable weighted sum on purpose so judges can see exactly why a score
was assigned.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.config import settings
from app.signals import SignalScores

WEIGHTS = {
    "rate": settings.weight_rate,
    "templates": settings.weight_templates,
    "reasoning": settings.weight_reasoning,
    "linked": settings.weight_linked,
    "coverage": settings.weight_coverage,
}


@dataclass(frozen=True)
class RiskResult:
    score: float  # 0-100
    breakdown: dict  # signal -> {value, weight, contribution}


def compute_risk(signals: SignalScores) -> RiskResult:
    values = {
        "rate": signals.rate,
        "templates": signals.templates,
        "reasoning": signals.reasoning,
        "linked": signals.linked,
        "coverage": signals.coverage,
    }
    breakdown = {}
    total = 0.0
    for name, value in values.items():
        weight = WEIGHTS[name]
        contribution = value * weight * 100
        breakdown[name] = {"value": round(value, 4), "weight": weight, "contribution": round(contribution, 2)}
        total += contribution
    return RiskResult(score=round(min(total, 100.0), 2), breakdown=breakdown)
