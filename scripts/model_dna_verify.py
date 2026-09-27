#!/usr/bin/env python
"""Model DNA verifier: sends known trap questions to a suspect endpoint,
counts how many trap phrases come back, and reports a binomial-test p-value
against an approximate chance-match rate.

Usage:
    python scripts/model_dna_verify.py --target clone
    python scripts/model_dna_verify.py --target clean

`clone` hits the /clone/chat/completions stand-in (expected: many matches).
`clean` calls the real upstream model backend directly, bypassing Puaro
entirely (expected: ~0 matches, since that model never saw any trap phrase).

Honesty notes:
  - The "chance match rate" (p0) used in the binomial test is the inverse of
    the trap-phrase word-combination space size (see app/decoys.py), NOT a
    measured natural-language statistic. It's a documented, conservative
    approximation for this demo, not a general accuracy claim.
  - All questions/answers here come from this repo's own synthetic demo
    traffic. This is not an independent benchmark.
"""
from __future__ import annotations

import argparse
import json
import sys

import httpx

sys.path.insert(0, ".")

from app.db import connection, init_db  # noqa: E402
from app.decoys import COMBINATION_SPACE_SIZE  # noqa: E402
from app.models.backend import complete as call_clean_model  # noqa: E402
from app.stats import binomial_sf  # noqa: E402

GATEWAY_URL = "http://127.0.0.1:8000"


def load_trap_questions(limit: int | None = None) -> list[dict]:
    init_db()
    with connection() as conn:
        query = "SELECT DISTINCT question_id, question_text, trap_phrase FROM trap_ledger ORDER BY created_at"
        rows = conn.execute(query).fetchall()
    rows = [dict(r) for r in rows]
    return rows[:limit] if limit else rows


def query_clone(question_text: str) -> str:
    resp = httpx.post(
        f"{GATEWAY_URL}/clone/chat/completions",
        json={"messages": [{"role": "user", "content": question_text}]},
        timeout=10.0,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def query_clean(question_text: str) -> str:
    return call_clean_model(question_text).text


def run_verification(target: str, limit: int | None = None) -> dict:
    traps = load_trap_questions(limit)
    if not traps:
        return {
            "target": target,
            "total": 0,
            "matches": 0,
            "p_value": None,
            "note": "no trap phrases recorded yet — send some decoy-tier traffic first",
        }

    query_fn = query_clone if target == "clone" else query_clean
    matches = 0
    details = []
    for trap in traps:
        try:
            output = query_fn(trap["question_text"])
        except Exception as exc:  # noqa: BLE001
            details.append({"question_id": trap["question_id"], "error": str(exc)})
            continue
        hit = trap["trap_phrase"] in output
        matches += int(hit)
        details.append({"question_id": trap["question_id"], "matched": hit})

    n = len(traps)
    p0 = 1.0 / COMBINATION_SPACE_SIZE
    p_value = binomial_sf(matches, n, p0)

    return {
        "target": target,
        "total": n,
        "matches": matches,
        "chance_match_rate_p0": p0,
        "p_value": p_value,
        "combination_space_size": COMBINATION_SPACE_SIZE,
        "details": details,
        "caveat": "p0 is an approximation from trap-phrase combinatorics, not a measured natural-language rate.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=["clone", "clean"], required=True)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    result = run_verification(args.target, args.limit)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
