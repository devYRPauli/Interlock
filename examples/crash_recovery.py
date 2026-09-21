"""
See it work. One refund, one crash, one receipt.

    python3 demo.py            # tier 2 (API has a lookup)
    python3 demo.py 3          # tier 3 (API has nothing) -> the honest AMBIGUOUS
    python3 demo.py naive      # today's baseline -> double refund
"""

import os
import sys
import tempfile
from typing import Optional

from interlock import Gate, Leases, Naive, SimulatedCrash
from interlock.targets import Payments


def main(arguments: Optional[list[str]] = None) -> None:
    arguments = sys.argv[1:] if arguments is None else arguments
    arg = arguments[0] if arguments else "2"
    naive = arg == "naive"
    tier = 3 if naive else int(arg)

    api = Payments(tier)
    api.create_order("881", 100)
    leases = Leases()
    leases.grant("L-refund")
    jpath = os.path.join(tempfile.mkdtemp(prefix="interlock-crash-demo-"), "journal.jsonl")
    system = Naive(api) if naive else Gate(api, jpath, leases)

    proposal = {
        "agent": "refund-bot",
        "lease": "L-refund",
        "request_id": "case-4471",
        "premises": api.capture("881"),
        "effect": {"order": "881", "amount": 20},
    }

    print(
        f"\n  system: {'NAIVE (no gate)' if naive else f'INTERLOCK, payments API at tier {tier}'}"
    )
    print(
        "  customer paid $100. case #4471 approves one $20 partial refund.\n  agent decides: refund $20\n"
    )
    print("  ── refund executes, then the process dies before the ack ──")
    try:
        system.submit(proposal, crash_after_effect=True)
    except SimulatedCrash:
        print("  💥 crash\n")

    print("  ── process restarts ──")
    rec = system.recover()
    if not rec:
        print("  naive has no memory of what it was doing. It retries.")
        system.submit(proposal)
    else:
        print(f"  journal says DISPATCHED with no COMMITTED → recovery: {list(rec.values())[0]}")

    print(
        f"\n  refunded on order #881: ${api.refunded_total('881')}  ({len(api.refunds_for('881'))} refund record(s))"
    )
    if not naive:
        print("\n  receipt:")
        for k, v in system.receipt(proposal).items():
            print(f"    {k:11} {v}")
        print(f"\n  journal ({jpath}):")
        for e in system.journal.entries():
            print(
                f"    {e['kind']:11} {e['effect_id']}  " + (e.get("via") or e.get("reason") or "")
            )
    print()


if __name__ == "__main__":
    main()
