"""Prompt template fingerprinting (MinHash) and reasoning-demand detection."""
from __future__ import annotations

import re

import numpy as np
from datasketch import MinHash

NUM_PERM = 32

_ENTITY_RE = re.compile(r"\d+|\"[^\"]*\"|'[^']*'")
_WORD_RE = re.compile(r"[a-z]+")

REASONING_PHRASES = [
    "step by step",
    "step-by-step",
    "chain of thought",
    "show your reasoning",
    "show your work",
    "explain your reasoning",
    "walk me through",
    "think through this",
    "reason through",
]


def normalize_for_template(text: str) -> str:
    """Strip specific entities (numbers, quoted strings) so near-identical
    templates with different filled-in values hash the same."""
    return _ENTITY_RE.sub(" ", text.lower())


def shingles(text: str, k: int = 3) -> set[str]:
    words = _WORD_RE.findall(normalize_for_template(text))
    if len(words) < k:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i : i + k]) for i in range(len(words) - k + 1)}


def compute_minhash(text: str) -> MinHash | None:
    """Returns None for text with no extractable shingles (empty/degenerate
    content). A MinHash that was never updated is a fixed, content-free
    value — every such prompt would otherwise appear identical to every
    other one via jaccard(), letting an attacker cheaply farm a "matching
    template" signal by sending empty or symbol-only content. None is
    treated as "no template signal" by the signals layer instead."""
    shingle_set = shingles(text)
    if not shingle_set:
        return None
    m = MinHash(num_perm=NUM_PERM)
    for shingle in shingle_set:
        m.update(shingle.encode("utf-8"))
    return m


def serialize_minhash(m: MinHash | None) -> str | None:
    if m is None:
        return None
    return ",".join(str(v) for v in m.hashvalues)


def deserialize_minhash(raw: str) -> MinHash:
    m = MinHash(num_perm=NUM_PERM)
    m.hashvalues = np.array([int(v) for v in raw.split(",")], dtype=np.uint64)
    return m


def jaccard(a: MinHash, b: MinHash) -> float:
    return a.jaccard(b)


def demands_reasoning(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in REASONING_PHRASES)
