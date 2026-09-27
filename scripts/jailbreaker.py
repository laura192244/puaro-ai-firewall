#!/usr/bin/env python
"""A few injection/jailbreak prompts, expected to be caught by the Firewall
step before ever reaching signals/risk/the model."""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from app.demo_actions import send_hacker  # noqa: E402


def main() -> None:
    print("Sending 4 jailbreak/injection attempts...")
    results = send_hacker(4)
    blocked = [r for r in results if r.status_code == 400]
    for r in results:
        print(f"  hacker -> HTTP {r.status_code} ({'blocked' if r.status_code == 400 else 'NOT BLOCKED'})")
    print(f"\n{len(blocked)}/{len(results)} blocked by the firewall.")


if __name__ == "__main__":
    main()
