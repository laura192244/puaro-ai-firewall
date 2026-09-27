"""Per-account signals computed over a sliding window, per PUARO_SIGNAL_WINDOW_SECONDS.

Each signal is normalized to 0.0-1.0 so app/risk.py can combine them with
transparent, fixed weights.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass

from app.config import settings
from app.db import connection
from app.templates import deserialize_minhash, jaccard
from app.topics import all_topics


@dataclass(frozen=True)
class SignalScores:
    rate: float
    templates: float
    reasoning: float
    linked: float
    coverage: float
    linked_account_ids: tuple[str, ...] = ()


def _window_cutoff() -> float:
    return time.time() - settings.signal_window_seconds


def compute_signals(
    *,
    account_id: str,
    tenant_id: str,
    fingerprint_hash: str,
    current_minhash,
    current_topics: list[str],
    current_reasoning_flag: bool,
) -> SignalScores:
    cutoff = _window_cutoff()
    with connection() as conn:
        history = conn.execute(
            """
            SELECT reasoning_requested, topics, minhash_signature
            FROM requests
            WHERE account_id = ? AND created_at >= ? AND firewall_blocked = 0
            """,
            (account_id, cutoff),
        ).fetchall()

        linked_rows = conn.execute(
            """
            SELECT DISTINCT account_id FROM requests
            WHERE tenant_id = ? AND fingerprint_hash = ? AND account_id != ? AND created_at >= ?
            """,
            (tenant_id, fingerprint_hash, account_id, cutoff),
        ).fetchall()

    total_requests = len(history) + 1
    rate = min(total_requests / settings.rate_cap_per_window, 1.0)

    reasoning_hits = sum(1 for row in history if row["reasoning_requested"]) + int(current_reasoning_flag)
    reasoning = reasoning_hits / total_requests

    templates = 0.0
    if current_minhash is not None:
        similar_count = 0
        for row in history:
            if not row["minhash_signature"]:
                continue
            prior_mh = deserialize_minhash(row["minhash_signature"])
            if jaccard(current_minhash, prior_mh) >= settings.template_similarity_threshold:
                similar_count += 1
        templates = min(similar_count / max(len(history), 1), 1.0) if history else 0.0

    linked_account_ids = tuple(row["account_id"] for row in linked_rows)
    linked = min(len(linked_account_ids) / settings.linked_account_cap, 1.0)

    seen_topics: set[str] = set(current_topics)
    for row in history:
        if row["topics"]:
            seen_topics.update(json.loads(row["topics"]))
    coverage = min(len(seen_topics) / len(all_topics()), 1.0)

    return SignalScores(
        rate=rate,
        templates=templates,
        reasoning=reasoning,
        linked=linked,
        coverage=coverage,
        linked_account_ids=linked_account_ids,
    )
