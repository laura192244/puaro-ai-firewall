import pytest

from app.stats import binomial_sf


def test_zero_matches_gives_p_value_one():
    assert binomial_sf(0, 10, 0.001) == 1.0


def test_all_matches_with_tiny_p0_gives_tiny_p_value():
    p = binomial_sf(10, 10, 0.001)
    assert p == pytest.approx(0.001**10, rel=1e-6)


def test_matches_exceeding_trials_is_impossible():
    assert binomial_sf(11, 10, 0.5) == 0.0


def test_monotonic_in_k():
    n, p = 20, 0.01
    values = [binomial_sf(k, n, p) for k in range(0, n + 1)]
    assert all(values[i] >= values[i + 1] for i in range(len(values) - 1))
