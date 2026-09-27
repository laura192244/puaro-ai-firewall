"""Response policy: maps a 0-100 risk score to an action.

    < threshold_slow            -> pass
    threshold_slow..hide-1      -> slow
    threshold_hide..decoy-1     -> hide_reasoning
    >= threshold_decoy          -> decoy

Hard blocks and account bans are NOT automatic — per the design, those need a
human "approve" click in the dashboard (Phase 6). This module only ever
returns the four soft actions above.
"""
from __future__ import annotations

from app.config import settings

PASS = "pass"
SLOW = "slow"
HIDE_REASONING = "hide_reasoning"
DECOY = "decoy"


def decide(risk_score: float) -> str:
    if risk_score >= settings.threshold_decoy:
        return DECOY
    if risk_score >= settings.threshold_hide_reasoning:
        return HIDE_REASONING
    if risk_score >= settings.threshold_slow:
        return SLOW
    return PASS
