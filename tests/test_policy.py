from app.policy import DECOY, HIDE_REASONING, PASS, SLOW, decide


def test_pass_below_slow_threshold():
    assert decide(0) == PASS
    assert decide(49.9) == PASS


def test_slow_band():
    assert decide(50) == SLOW
    assert decide(54.9) == SLOW


def test_hide_reasoning_band():
    assert decide(55) == HIDE_REASONING
    assert decide(69.9) == HIDE_REASONING


def test_decoy_band():
    assert decide(70) == DECOY
    assert decide(100) == DECOY
