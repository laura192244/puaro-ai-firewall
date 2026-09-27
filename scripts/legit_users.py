#!/usr/bin/env python
"""Several normal users, plus one heavy but legitimate Dev CI account.
Dev CI must not be punished despite high volume and a repeated template —
see app/config.py's threshold_slow comment for why that's true today."""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from app.demo_actions import send_client, send_dev_ci  # noqa: E402


def main() -> None:
    print("Sending 6 normal client requests (Alice/Bob, varied topics)...")
    for r in send_client(6):
        print(f"  {r.persona:8s} -> {r.outcome or r.status_code} (risk={r.risk_score})")

    print("\nSending 20 Dev CI requests (same template, own origin)...")
    results = send_dev_ci(20)
    punished = [r for r in results if r.outcome not in ("answered", None)]
    for r in results[-5:]:
        print(f"  dev-ci -> {r.outcome} (risk={r.risk_score})")
    if punished:
        print(f"\nWARNING: Dev CI was punished on {len(punished)}/{len(results)} requests.")
    else:
        print(f"\nDev CI was never punished across {len(results)} requests. Good.")


if __name__ == "__main__":
    main()
