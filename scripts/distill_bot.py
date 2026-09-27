#!/usr/bin/env python
"""5-10 fresh accounts sending templated, reasoning-demanding prompts across
many topics, all sharing one botnet origin (IP + User-Agent) — the linked-
accounts signal is what a real distillation farm looks like from the outside.

Splitting volume across 8 accounts (instead of hammering from one) is a real
evasion tactic, so it genuinely takes more total requests before any single
account's own signals accumulate enough to cross the decoy threshold — see
the comment on app.demo_actions.run_full_demo for the measured number.
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from app.demo_actions import send_bot_burst  # noqa: E402


def main() -> None:
    print("Sending bot bursts (8 accounts, shared origin, reasoning-demand, topic sweep)...")
    total_sent = 0
    first_decoy_at = None
    for burst in range(20):
        start_at = total_sent + 1
        batch = send_bot_burst(8, start_at=start_at)
        total_sent += len(batch)
        last = batch[-1]
        print(f"  requests {start_at:3d}-{total_sent:3d}: last outcome={last.outcome} (risk={last.risk_score})")
        if any(r.outcome == "decoy" for r in batch):
            first_decoy_at = total_sent
            print(f"\nFirst decoy reached after {total_sent} bot requests.")
            break

    if first_decoy_at is None:
        print(f"\nNo decoy reached within {total_sent} requests — try increasing the burst count.")


if __name__ == "__main__":
    main()
