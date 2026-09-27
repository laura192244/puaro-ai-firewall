"""Minimal binomial test (no scipy dependency needed for n this small)."""
from __future__ import annotations

import math


def binomial_sf(k: int, n: int, p: float) -> float:
    """P(X >= k) for X ~ Binomial(n, p). Exact via math.comb; fine for n <= a few hundred."""
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    return sum(math.comb(n, i) * (p**i) * ((1 - p) ** (n - i)) for i in range(k, n + 1))
