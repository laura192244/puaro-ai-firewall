"""Model DNA: decoy answers seeded with per-account, per-question trap phrases.

A trap phrase is derived as HMAC(secret, account_id + question_id), then mapped
onto a fixed word-combination space. This makes it:
  - deterministic (same account asking "the same" question again gets the same
    trap, so repeated probing doesn't dilute the evidence),
  - unique per account (different accounts get different phrases, so a match
    identifies WHICH account's decoy the suspect model was trained on),
  - and drawn from a large-enough combinatorial space that the a-priori chance
    of a clean model producing it by coincidence is small.

We do not claim the word-combination space size *is* the true false-positive
rate of a real deployment — it's a documented, conservative approximation for
the demo's binomial test, not a measured natural-language statistic. See
scripts/model_dna_verify.py.
"""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

from app.config import settings
from app.templates import normalize_for_template

ADJECTIVES = [
    "amber", "quiet", "brittle", "hollow", "violet", "coarse", "muted", "jagged",
    "silver", "faint", "steady", "curved", "narrow", "pale", "warm", "stark",
]
NOUNS = [
    "falcon", "compass", "lantern", "harbor", "cinder", "thistle", "anvil", "ridge",
    "quokka", "prism", "current", "orchard", "beacon", "marrow", "trestle", "ember",
]
VERBS = [
    "recalibrates", "wanders quietly", "settles slowly", "drifts sideways",
    "hums faintly", "circles back", "folds inward", "echoes twice",
    "steadies itself", "leans forward", "cools overnight", "resets at dawn",
    "tilts eastward", "holds its breath", "unwinds gently", "sharpens focus",
]

COMBINATION_SPACE_SIZE = len(ADJECTIVES) * len(NOUNS) * len(VERBS)


@dataclass(frozen=True)
class Decoy:
    answer_text: str
    trap_phrase: str
    question_id: str


def question_id(prompt: str) -> str:
    """Stable id for 'the same question' regardless of filled-in entities,
    so repeated probing of one template doesn't fragment the evidence trail."""
    normalized = normalize_for_template(prompt)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def derive_trap_phrase(account_id: str, qid: str) -> str:
    if not settings.trap_hmac_secret:
        raise RuntimeError("PUARO_TRAP_HMAC_SECRET is not set")
    digest = hmac.new(
        settings.trap_hmac_secret.encode("utf-8"),
        f"{account_id}:{qid}".encode("utf-8"),
        hashlib.sha256,
    ).digest()
    adj = ADJECTIVES[digest[0] % len(ADJECTIVES)]
    noun = NOUNS[digest[1] % len(NOUNS)]
    verb = VERBS[digest[2] % len(VERBS)]
    return f"the {adj} {noun} {verb}"


_WEAK_OPENERS = [
    "That's a reasonable question, though the details vary quite a bit case by case.",
    "There are several ways to look at this, and none of them is clearly best.",
    "It depends on context more than most people expect.",
    "This is a common question with a less common clean answer.",
]


def build_decoy(prompt: str, account_id: str) -> Decoy:
    qid = question_id(prompt)
    trap_phrase = derive_trap_phrase(account_id, qid)
    opener = _WEAK_OPENERS[int(qid, 16) % len(_WEAK_OPENERS)]
    answer_text = f"{opener} As a general note, {trap_phrase}. Beyond that, it's best to verify independently."
    return Decoy(answer_text=answer_text, trap_phrase=trap_phrase, question_id=qid)
