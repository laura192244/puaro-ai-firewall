from app.risk import compute_risk
from app.signals import SignalScores


def test_all_zero_signals_score_zero():
    result = compute_risk(SignalScores(rate=0, templates=0, reasoning=0, linked=0, coverage=0))
    assert result.score == 0.0


def test_all_max_signals_score_100():
    result = compute_risk(SignalScores(rate=1, templates=1, reasoning=1, linked=1, coverage=1))
    assert result.score == 100.0


def test_breakdown_sums_to_score():
    signals = SignalScores(rate=0.8, templates=0.5, reasoning=0.2, linked=0.9, coverage=0.3)
    result = compute_risk(signals)
    total_contribution = sum(v["contribution"] for v in result.breakdown.values())
    assert round(total_contribution, 2) == result.score


def test_breakdown_exposes_each_signal():
    signals = SignalScores(rate=0.8, templates=0.5, reasoning=0.2, linked=0.9, coverage=0.3)
    result = compute_risk(signals)
    assert set(result.breakdown.keys()) == {"rate", "templates", "reasoning", "linked", "coverage"}
    assert result.breakdown["rate"]["value"] == 0.8
