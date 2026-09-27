from app.templates import (
    compute_minhash,
    demands_reasoning,
    deserialize_minhash,
    jaccard,
    serialize_minhash,
)


def test_identical_text_has_jaccard_one():
    a = compute_minhash("Explain how photosynthesis works in plants")
    b = compute_minhash("Explain how photosynthesis works in plants")
    assert jaccard(a, b) == 1.0


def test_same_template_different_entities_is_similar():
    a = compute_minhash("What is the capital of France")
    b = compute_minhash("What is the capital of Japan")
    assert jaccard(a, b) > 0.5


def test_unrelated_text_is_dissimilar():
    a = compute_minhash("What is the capital of France")
    b = compute_minhash("Write a recipe for chocolate cake with detailed baking instructions")
    assert jaccard(a, b) < 0.3


def test_serialize_round_trip_preserves_jaccard():
    a = compute_minhash("Explain quantum entanglement step by step")
    serialized = serialize_minhash(a)
    restored = deserialize_minhash(serialized)
    assert jaccard(a, restored) == 1.0


def test_demands_reasoning_detects_phrase():
    assert demands_reasoning("Please explain step by step how this works") is True
    assert demands_reasoning("What's the weather like today?") is False


def test_empty_content_has_no_minhash():
    """Regression test: two empty/degenerate prompts must NOT look identical
    to each other via jaccard(). An unupdated MinHash is a fixed value, so
    every empty-content request would otherwise spuriously match every other
    one at similarity 1.0, letting an attacker farm the templates signal with
    zero real content."""
    assert compute_minhash("") is None
    assert compute_minhash("   ") is None
    assert compute_minhash("123 456") is None  # only digits -> stripped to nothing


def test_serialize_none_minhash_is_none():
    assert serialize_minhash(None) is None
