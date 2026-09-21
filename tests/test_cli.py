"""User-facing command contracts: help, argument errors, and verification exit codes."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from interlock import Gate, Leases
from interlock.targets import Payments

ROOT = Path(__file__).resolve().parents[1]


class CommandLine(unittest.TestCase):
    def command(self, module, *arguments):
        return subprocess.run(
            [sys.executable, "-m", module, *arguments],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=10,
        )

    def test_commands_explain_their_usage_without_starting_a_server(self):
        for module in ("interlock.mcp_proxy", "interlock.receipts"):
            with self.subTest(module=module):
                result = self.command(module, "--help")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("usage:", result.stdout)

    def test_invalid_arguments_are_usage_errors_without_tracebacks(self):
        for module, arguments in (
            ("interlock.mcp_proxy", []),
            ("interlock.mcp_proxy", ["--config"]),
            ("interlock.mcp_proxy", ["--config", "unused.json", "--"]),
            ("interlock.receipts", []),
            ("interlock.receipts", ["unused.json", "--key"]),
        ):
            with self.subTest(module=module, arguments=arguments):
                result = self.command(module, *arguments)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("usage:", result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_verification_exit_code_matches_valid_and_tampered_receipts(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Payments(2)
            target.create_order("order", 100)
            leases = Leases()
            leases.grant("approval")
            gate = Gate(target, str(Path(directory) / "journal.jsonl"), leases)
            proposal = {
                "agent": "cli-test",
                "lease": "approval",
                "request_id": "request",
                "premises": target.capture("order"),
                "effect": {"order": "order", "amount": 20},
            }
            self.assertEqual(gate.submit(proposal), "COMMITTED")
            receipt = gate.receipt_bundle(proposal)
            path = Path(directory) / "receipt.json"
            path.write_text(json.dumps(receipt), encoding="utf-8")
            result = self.command("interlock.receipts", str(path))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(result.stdout)["valid"])

            receipt["entries"][0]["effect"]["amount"] = 99
            path.write_text(json.dumps(receipt), encoding="utf-8")
            result = self.command("interlock.receipts", str(path))
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertFalse(json.loads(result.stdout)["valid"])


if __name__ == "__main__":
    unittest.main()
