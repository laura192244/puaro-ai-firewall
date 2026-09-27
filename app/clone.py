"""Clone stand-in: answers by exact-match-then-nearest-neighbor lookup over
harvested (question, answer) pairs, exactly as a real distillation bot's copy
would if it had simply memorized/parroted what it scraped from Puaro. We do
not train a real model — this stands in for one, and the dashboard/API must
label it as such.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.db import connection
from app.templates import compute_minhash, deserialize_minhash, jaccard

MATCH_THRESHOLD = 0.3
_WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class CloneResponse:
    answer_text: str
    matched: bool
    similarity: float
    exact_match: bool = False


def _normalize_exact(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text.strip().lower())


def answer(prompt: str) -> CloneResponse:
    with connection() as conn:
        rows = conn.execute(
            "SELECT prompt_text, answer_text, minhash_signature FROM requests "
            "WHERE firewall_blocked = 0 AND answer_text IS NOT NULL AND minhash_signature IS NOT NULL "
            "ORDER BY created_at DESC"
        ).fetchall()

    # An attacker's scraped dataset is a literal (question, answer) cache: if they
    # ask the exact same question again, they get back exactly what they scraped
    # before, whatever tier it was served at (real or decoy). Try that first,
    # before falling back to fuzzy template similarity for genuinely new questions.
    normalized_query = _normalize_exact(prompt)
    for row in rows:
        if row["prompt_text"] and _normalize_exact(row["prompt_text"]) == normalized_query:
            return CloneResponse(answer_text=row["answer_text"], matched=True, similarity=1.0, exact_match=True)

    query_mh = compute_minhash(prompt)
    best_similarity = 0.0
    best_answer = None
    for row in rows:
        candidate_mh = deserialize_minhash(row["minhash_signature"])
        similarity = jaccard(query_mh, candidate_mh)
        if similarity > best_similarity:
            best_similarity = similarity
            best_answer = row["answer_text"]

    if best_answer is not None and best_similarity >= MATCH_THRESHOLD:
        return CloneResponse(answer_text=best_answer, matched=True, similarity=best_similarity)
    return CloneResponse(
        answer_text="(no sufficiently similar harvested question — the clone has nothing to parrot here)",
        matched=False,
        similarity=best_similarity,
    )
