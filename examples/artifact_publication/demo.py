"""Run the local example and leave inspectable provider state and journal receipts."""

import argparse
import json
import tempfile
import time
from pathlib import Path
from typing import Any

from interlock import Interlock, SimulatedCrash
from interlock.receipts import verify
from interlock.tools import gated, run

from .configuration import configuration
from .mcp_server import call_tool
from .models import PublicationRequest
from .storage import ArtifactStore


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--directory", help="New directory for the demo; defaults to a temporary directory"
    )
    args = parser.parse_args()
    directory = (
        Path(args.directory)
        if args.directory
        else Path(tempfile.mkdtemp(prefix="interlock-artifacts-"))
    )
    if args.directory:
        directory.mkdir(parents=True, exist_ok=False)
    store = ArtifactStore(directory / "artifacts.sqlite")
    store.initialize()
    config = configuration(directory.resolve() / "journal")
    (directory / "interlock.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    original: PublicationRequest = dict(
        request_id="research-001",
        name="reports/evaluation.md",
        expected_version=0,
        content="Initial research report.\n",
        approval_id="review-001",
    )
    store.approve(original, expires=time.time() + 3600)

    def install() -> Any:
        gate = Interlock(config["journal_dir"])
        call = gated(
            gate,
            "publish_artifact",
            config["tools"]["publish_artifact"],
            lambda name, arguments: call_tool(store, name, arguments),
            module="artifact_demo",
        )
        return call

    call = install()
    proposal = call.proposal(original)
    try:
        call.gate.submit(proposal, crash_after_effect=True)
    except SimulatedCrash:
        pass
    newer: PublicationRequest = dict(
        request_id="research-002",
        name=original["name"],
        expected_version=1,
        content="Newer report reviewed by another operator.\n",
        approval_id="review-002",
    )
    store.approve(newer, expires=time.time() + 3600)
    store.publish_artifact(**newer, reference="operator-publication-002")
    recovered = install()
    outcome = run(recovered, original)
    receipt = recovered.gate.receipt_bundle(proposal)
    checked = verify(receipt)
    current = store.get_artifact(original["name"])
    if outcome["status"] != "COMMITTED_ON_QUERY" or current["version"] != 2 or not checked["valid"]:
        raise RuntimeError(f"Demo invariant failed: {outcome!r}, {current!r}, {checked!r}")
    (directory / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "directory": str(directory.resolve()),
                "crash": "simulated after commit, before acknowledgement",
                "recovery": outcome["status"],
                "current_artifact": current,
                "receipt_valid": checked["valid"],
                "original_happened": checked["happened"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
