"""Hashing helpers. API keys, IPs and fingerprints are never stored in the clear."""
from __future__ import annotations

import hashlib


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_api_key(api_key: str) -> str:
    return sha256_hex(f"apikey:{api_key}")


def account_id_from_key(tenant_id: str, label: str) -> str:
    return sha256_hex(f"account:{tenant_id}:{label}")[:16]


def origin_fingerprint(*, ip: str, user_agent: str) -> str:
    """Hash of IP + user agent only — deliberately excludes the account's own
    API key so that multiple different accounts calling from the same origin
    (the bot-farm pattern) hash to the SAME fingerprint and can be linked.
    This is also what Phase 5 collective immunity shares across tenants.
    """
    return sha256_hex(f"origin:{ip}:{user_agent}")
