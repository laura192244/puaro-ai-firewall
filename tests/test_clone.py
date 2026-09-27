import time

import pytest

from app import db as db_module
from app.clone import answer as clone_answer
from app.templates import compute_minhash, serialize_minhash


@pytest.fixture()
def temp_db(tmp_path):
    db_path = tmp_path / "clone_test.db"
    original = db_module.settings.db_path
    object.__setattr__(db_module.settings, "db_path", str(db_path))
    db_module.init_db()
    try:
        yield db_path
    finally:
        object.__setattr__(db_module.settings, "db_path", original)


def _insert_harvested(conn, *, request_id, prompt, answer_text):
    mh = serialize_minhash(compute_minhash(prompt))
    conn.execute(
        """
        INSERT INTO requests (
            request_id, account_id, tenant_id, created_at, prompt_text, answer_text,
            fingerprint_hash, firewall_blocked, firewall_reason, firewall_engine,
            outcome, minhash_signature
        ) VALUES (?, 'acc1', 'custA', ?, ?, ?, 'fp1', 0, 'clean', 'fallback:regex', 'decoy', ?)
        """,
        (request_id, time.time(), prompt, answer_text, mh),
    )


def test_clone_echoes_harvested_answer_for_similar_question(temp_db):
    with db_module.connection() as conn:
        _insert_harvested(
            conn,
            request_id="r1",
            prompt="What is the capital of France",
            answer_text="the amber falcon recalibrates quietly (decoy trap answer)",
        )
    result = clone_answer("What is the capital of Germany")
    assert result.matched is True
    assert "amber falcon" in result.answer_text


def test_clone_prefers_exact_match_over_fuzzy_template_match(temp_db):
    with db_module.connection() as conn:
        _insert_harvested(
            conn,
            request_id="r1",
            prompt="Run integration test suite iteration 1 for the checkout service",
            answer_text="real answer for iteration 1",
        )
        _insert_harvested(
            conn,
            request_id="r2",
            prompt="Run integration test suite iteration 2 for the checkout service",
            answer_text="the amber falcon recalibrates quietly (decoy for iteration 2)",
        )
    # Same template as both rows (digits differ), but exact text matches r1.
    result = clone_answer("Run integration test suite iteration 1 for the checkout service")
    assert result.exact_match is True
    assert result.answer_text == "real answer for iteration 1"


def test_clone_reports_no_match_for_unrelated_question(temp_db):
    with db_module.connection() as conn:
        _insert_harvested(
            conn,
            request_id="r1",
            prompt="What is the capital of France",
            answer_text="the amber falcon recalibrates quietly",
        )
    result = clone_answer("Write a full symphony score in the style of Beethoven")
    assert result.matched is False
