"""Collective immunity: an attacker fingerprint confirmed at one tenant is
blocked at every tenant on its very first request there — no history needed.

Only the hashed origin fingerprint (IP+UA hash, see app/fingerprint.py) and a
free-text reason are shared. Prompts, answers and account identities are never
written to this table.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from app.db import connection


@dataclass(frozen=True)
class ImmunityRecord:
    fingerprint_hash: str
    origin_tenant_id: str
    reason: str
    created_at: float


def publish(fingerprint_hash: str, origin_tenant_id: str, reason: str) -> None:
    """Idempotent: the first tenant to confirm a fingerprint owns the record."""
    with connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO shared_fingerprints (fingerprint_hash, origin_tenant_id, reason, created_at) "
            "VALUES (?, ?, ?, ?)",
            (fingerprint_hash, origin_tenant_id, reason, time.time()),
        )


def lookup(fingerprint_hash: str) -> ImmunityRecord | None:
    with connection() as conn:
        row = conn.execute(
            "SELECT fingerprint_hash, origin_tenant_id, reason, created_at FROM shared_fingerprints "
            "WHERE fingerprint_hash = ?",
            (fingerprint_hash,),
        ).fetchone()
    if row is None:
        return None
    return ImmunityRecord(**dict(row))
