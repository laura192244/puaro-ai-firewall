import json
import time

import pytest

from app import db as db_module
from app.config import settings
from app.signals import compute_signals
from app.templates import compute_minhash


@pytest.fixture()
def temp_db(tmp_path):
    db_path = tmp_path / "signals_test.db"
    original = db_module.settings.db_path
    object.__setattr__(db_module.settings, "db_path", str(db_path))
    db_module.init_db()
    try:
        yield db_path
    finally:
        object.__setattr__(db_module.settings, "db_path", original)


def _insert(conn, *, account_id, tenant_id, fingerprint_hash, minhash_sig, topics, reasoning, created_at):
    conn.execute(
        """
        INSERT INTO requests (
            request_id, account_id, tenant_id, created_at, prompt_text, fingerprint_hash,
            firewall_blocked, firewall_reason, firewall_engine, outcome,
            reasoning_requested, topics, minhash_signature
        ) VALUES (?, ?, ?, ?, ?, ?, 0, 'clean', 'fallback:regex', 'answered', ?, ?, ?)
        """,
        (
            f"req-{account_id}-{created_at}",
            account_id,
            tenant_id,
            created_at,
            "prompt",
            fingerprint_hash,
            int(reasoning),
            json.dumps(topics),
            minhash_sig,
        ),
    )


def test_rate_signal_scales_with_request_count(temp_db):
    with db_module.connection() as conn:
        now = time.time()
        for i in range(9):
            _insert(
                conn,
                account_id="acc1",
                tenant_id="custA",
                fingerprint_hash="fp1",
                minhash_sig=None,
                topics=["other"],
                reasoning=False,
                created_at=now - i,
            )
    mh = compute_minhash("hello")
    signals = compute_signals(
        account_id="acc1",
        tenant_id="custA",
        fingerprint_hash="fp1",
        current_minhash=mh,
        current_topics=["other"],
        current_reasoning_flag=False,
    )
    # 9 history + 1 current = 10 requests; default rate_cap_per_window=20 -> 0.5
    assert signals.rate == pytest.approx(10 / settings.rate_cap_per_window)


def test_linked_signal_counts_other_accounts_same_fingerprint(temp_db):
    with db_module.connection() as conn:
        now = time.time()
        for label in ["bot1", "bot2", "bot3"]:
            _insert(
                conn,
                account_id=label,
                tenant_id="custA",
                fingerprint_hash="shared-fp",
                minhash_sig=None,
                topics=["other"],
                reasoning=False,
                created_at=now,
            )
    mh = compute_minhash("hello")
    signals = compute_signals(
        account_id="victim-account",
        tenant_id="custA",
        fingerprint_hash="shared-fp",
        current_minhash=mh,
        current_topics=["other"],
        current_reasoning_flag=False,
    )
    assert len(signals.linked_account_ids) == 3
    assert signals.linked == 1.0  # capped at linked_account_cap=3


def test_reasoning_signal_reflects_history_and_current(temp_db):
    with db_module.connection() as conn:
        now = time.time()
        _insert(
            conn,
            account_id="acc1",
            tenant_id="custA",
            fingerprint_hash="fp1",
            minhash_sig=None,
            topics=["other"],
            reasoning=True,
            created_at=now,
        )
    mh = compute_minhash("hello")
    signals = compute_signals(
        account_id="acc1",
        tenant_id="custA",
        fingerprint_hash="fp1",
        current_minhash=mh,
        current_topics=["other"],
        current_reasoning_flag=False,
    )
    assert signals.reasoning == 0.5  # 1 of 2 requests demanded reasoning


def test_coverage_signal_counts_distinct_topics(temp_db):
    from app.templates import serialize_minhash
    from app.topics import all_topics

    with db_module.connection() as conn:
        now = time.time()
        for i, topic in enumerate(["coding", "finance", "health"]):
            _insert(
                conn,
                account_id="acc1",
                tenant_id="custA",
                fingerprint_hash="fp1",
                minhash_sig=serialize_minhash(compute_minhash(topic)),
                topics=[topic],
                reasoning=False,
                created_at=now - i,
            )
    mh = compute_minhash("legal contract")
    signals = compute_signals(
        account_id="acc1",
        tenant_id="custA",
        fingerprint_hash="fp1",
        current_minhash=mh,
        current_topics=["legal"],
        current_reasoning_flag=False,
    )
    assert signals.coverage == pytest.approx(4 / len(all_topics()))


def test_none_minhash_contributes_zero_templates_signal(temp_db):
    """Regression test: an empty-content current request (current_minhash=None)
    must not match anything, even other empty-content history rows."""
    with db_module.connection() as conn:
        now = time.time()
        for i in range(5):
            _insert(
                conn,
                account_id="acc1",
                tenant_id="custA",
                fingerprint_hash="fp1",
                minhash_sig=None,  # these rows also had empty/degenerate content
                topics=["other"],
                reasoning=False,
                created_at=now - i,
            )
    signals = compute_signals(
        account_id="acc1",
        tenant_id="custA",
        fingerprint_hash="fp1",
        current_minhash=None,
        current_topics=["other"],
        current_reasoning_flag=False,
    )
    assert signals.templates == 0.0
