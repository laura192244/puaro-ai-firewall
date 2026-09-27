from app.decoys import build_decoy, derive_trap_phrase, question_id


def test_question_id_stable_across_numeric_entities():
    a = question_id("Run integration test suite iteration 1 for the checkout service")
    b = question_id("Run integration test suite iteration 42 for the checkout service")
    assert a == b


def test_question_id_differs_for_different_templates():
    a = question_id("What is the capital of France")
    b = question_id("How do I bake a cake")
    assert a != b


def test_trap_phrase_deterministic():
    qid = question_id("What is the capital of France")
    p1 = derive_trap_phrase("acc1", qid)
    p2 = derive_trap_phrase("acc1", qid)
    assert p1 == p2


def test_trap_phrase_differs_per_account():
    qid = question_id("What is the capital of France")
    p1 = derive_trap_phrase("acc1", qid)
    p2 = derive_trap_phrase("acc2", qid)
    assert p1 != p2


def test_build_decoy_embeds_trap_phrase():
    decoy = build_decoy("What is the capital of France", "acc1")
    assert decoy.trap_phrase in decoy.answer_text
