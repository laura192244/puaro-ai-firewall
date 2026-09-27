import pytest

from app import db as db_module
from app.immunity import lookup, publish


@pytest.fixture()
def temp_db(tmp_path):
    db_path = tmp_path / "immunity_test.db"
    original = db_module.settings.db_path
    object.__setattr__(db_module.settings, "db_path", str(db_path))
    db_module.init_db()
    try:
        yield db_path
    finally:
        object.__setattr__(db_module.settings, "db_path", original)


def test_lookup_returns_none_for_unknown_fingerprint(temp_db):
    assert lookup("unknown-fp") is None


def test_publish_then_lookup_finds_record(temp_db):
    publish("bad-fp", "custA", "confirmed distillation behavior")
    record = lookup("bad-fp")
    assert record is not None
    assert record.origin_tenant_id == "custA"
    assert record.reason == "confirmed distillation behavior"


def test_publish_is_idempotent_first_writer_wins(temp_db):
    publish("bad-fp", "custA", "first reason")
    publish("bad-fp", "custB", "second reason")
    record = lookup("bad-fp")
    assert record.origin_tenant_id == "custA"
    assert record.reason == "first reason"
