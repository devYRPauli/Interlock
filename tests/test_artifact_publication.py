"""Provider constraints, gate recovery, and killed MCP subprocesses for the local example."""

import json
import os
import sqlite3
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from examples.artifact_publication.configuration import configuration
from examples.artifact_publication.mcp_server import call_tool as mcp_call
from examples.artifact_publication.mcp_server import tool_functions
from examples.artifact_publication.models import PublicationRejected
from examples.artifact_publication.storage import ArtifactStore
from interlock import Interlock, SimulatedCrash, effect_id_for
from interlock.receipts import verify
from interlock.tools import gated, run
from support.mcp_session import Session


class Fixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.store = ArtifactStore(self.directory / "artifacts.sqlite")
        self.store.initialize()
        self.arguments = dict(
            request_id="request-1",
            name="reports/evaluation.md",
            expected_version=0,
            content="Reviewed report.\n",
            approval_id="review-1",
        )
        self.store.approve(self.arguments, expires=time.time() + 3600)

    def newer(self, version=1):
        arguments = dict(
            self.arguments,
            request_id="request-2",
            approval_id="review-2",
            expected_version=version,
            content="Newer reviewed report.\n",
        )
        self.store.approve(arguments, expires=time.time() + 3600)
        return self.store.publish_artifact(**arguments, reference="human-2")

    def install(self, call_tool=None):
        config = configuration(self.directory / "journal")
        return gated(
            Interlock(config["journal_dir"]),
            "publish_artifact",
            config["tools"]["publish_artifact"],
            call_tool or (lambda name, arguments: mcp_call(self.store, name, arguments)),
            module="artifact_tests",
        )

    def history_count(self):
        with self.store.connect() as db:
            return db.execute("SELECT COUNT(*) FROM publications").fetchone()[0]


class ArtifactStoreTests(Fixture):
    def test_retry_returns_historic_result_and_preserves_newer_content(self):
        # A careful provider-native baseline also preserves the invariant without Interlock.
        first = self.store.publish_artifact(**self.arguments, reference="original")
        self.newer()
        self.store.revoke(self.arguments["approval_id"])
        self.assertEqual(self.store.publish_artifact(**self.arguments, reference="original"), first)
        self.assertEqual(self.store.find_publication("original")["publication"], first)
        self.assertEqual(self.store.get_artifact(self.arguments["name"])["version"], 2)
        self.assertEqual(self.history_count(), 2)

    def test_reference_cannot_be_reused_with_a_changed_payload(self):
        self.store.publish_artifact(**self.arguments, reference="original")
        with self.assertRaisesRegex(PublicationRejected, "another payload"):
            self.store.publish_artifact(
                **dict(self.arguments, content="Changed"), reference="original"
            )
        self.assertEqual(self.history_count(), 1)

    def test_request_cannot_be_republished_with_a_new_reference(self):
        self.store.publish_artifact(**self.arguments, reference="original")
        with self.assertRaisesRegex(PublicationRejected, "request_id already published"):
            self.store.publish_artifact(**self.arguments, reference="new-reference")
        self.assertEqual(self.history_count(), 1)

    def test_approval_binds_the_exact_payload(self):
        for change in (
            {"content": "Unreviewed"},
            {"name": "other"},
            {"request_id": "other"},
            {"expected_version": 3},
        ):
            with (
                self.subTest(change=change),
                self.assertRaisesRegex(PublicationRejected, "operator-approved"),
            ):
                self.store.publish_artifact(**dict(self.arguments, **change), reference="original")
        self.assertEqual(self.history_count(), 0)

    def test_approval_is_immutable(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.approve(dict(self.arguments, content="Changed"), expires=time.time() + 3600)
        self.assertEqual(self.store.get_approval("review-1")["match"], self.arguments)

    def test_expired_and_revoked_approvals_do_not_publish(self):
        with patch(
            "examples.artifact_publication.storage.time.time", return_value=time.time() + 7200
        ):
            with self.assertRaisesRegex(PublicationRejected, "expired"):
                self.store.publish_artifact(**self.arguments, reference="expired")
        self.store.revoke("review-1")
        self.assertEqual(self.store.get_approval("review-1"), {})
        with self.assertRaisesRegex(PublicationRejected, "revoked"):
            self.store.publish_artifact(**self.arguments, reference="revoked")
        self.assertEqual(self.history_count(), 0)

    def test_invalid_versions_are_rejected(self):
        for version in (True, -1, 0.0, "0", None):
            with self.subTest(version=version), self.assertRaises(PublicationRejected):
                self.store.publish_artifact(
                    **dict(self.arguments, expected_version=version), reference="original"
                )
        self.assertEqual(self.history_count(), 0)

    def test_missing_database_is_not_recreated_as_empty_history(self):
        missing = ArtifactStore(self.directory / "missing.sqlite")
        with self.assertRaises(sqlite3.OperationalError):
            missing.find_publication("original")
        self.assertFalse(missing.path.exists())

    def test_concurrent_writers_using_one_version_have_one_winner(self):
        other = dict(self.arguments, request_id="other", approval_id="other", content="Other")
        self.store.approve(other, expires=time.time() + 3600)
        barrier = threading.Barrier(2)

        def publish(arguments):
            barrier.wait(timeout=5)
            try:
                return ArtifactStore(self.store.path).publish_artifact(
                    **arguments, reference=arguments["request_id"]
                )
            except PublicationRejected as error:
                return str(error)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(publish, (self.arguments, other)))
        self.assertEqual(sum(isinstance(result, dict) for result in results), 1, results)
        self.assertIn("version conflict: expected 0, current 1", results)
        self.assertEqual(self.history_count(), 1)


class ArtifactRecovery(Fixture):
    def test_lost_ack_then_newer_publication_recovers_original_history(self):
        call = self.install()
        proposal = call.proposal(self.arguments)
        with self.assertRaises(SimulatedCrash):
            call.gate.submit(proposal, crash_after_effect=True)
        self.newer()
        recovered = self.install()
        outcome = run(recovered, self.arguments)
        self.assertEqual(outcome["status"], "COMMITTED_ON_QUERY")
        self.assertEqual(self.store.get_artifact(self.arguments["name"])["version"], 2)
        self.assertEqual(self.history_count(), 2)
        checked = verify(recovered.gate.receipt_bundle(proposal))
        self.assertTrue(checked["valid"], checked)
        self.assertTrue(checked["happened"])
        self.assertTrue(checked["authorized_when_fired"])

    def test_crash_before_send_then_newer_publication_refuses_stale_decision(self):
        call = self.install()
        with self.assertRaises(SimulatedCrash):
            call.gate.submit(call.proposal(self.arguments), crash_before_effect=True)
        self.newer(version=0)
        outcome = run(self.install(), self.arguments)
        self.assertEqual(outcome["status"], "REFUSED:stale_premise_at_recovery")
        self.assertEqual(self.history_count(), 1)

    def test_crash_before_send_recovers_once_when_world_is_unchanged(self):
        call = self.install()
        with self.assertRaises(SimulatedCrash):
            call.gate.submit(call.proposal(self.arguments), crash_before_effect=True)
        restarted = self.install()
        self.assertEqual(run(restarted, self.arguments)["status"], "REAPPLIED_AFTER_QUERY")
        self.assertEqual(run(restarted, self.arguments)["status"], "DUPLICATE_IGNORED")
        self.assertEqual(self.history_count(), 1)

    def test_concurrent_gate_instances_publish_once(self):
        calls = (self.install(), self.install())
        barrier = threading.Barrier(2)

        def send(call):
            barrier.wait(timeout=5)
            return run(call, self.arguments)

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(send, calls))
        self.assertTrue(any(outcome["ok"] for outcome in outcomes), outcomes)
        self.assertTrue(
            all(
                outcome["status"] in ("COMMITTED", "DUPLICATE_IGNORED", "IN_FLIGHT")
                for outcome in outcomes
            ),
            outcomes,
        )
        self.assertEqual(self.history_count(), 1)

    def test_change_between_preflight_and_write_is_rejected_atomically(self):
        def interleave(name, arguments):
            if name == "publish_artifact":
                self.newer(version=0)
            return mcp_call(self.store, name, arguments)

        outcome = run(self.install(interleave), self.arguments)
        self.assertEqual(outcome["status"], "REFUSED:target_error")
        self.assertEqual(
            self.store.get_artifact(self.arguments["name"])["content"], "Newer reviewed report.\n"
        )
        self.assertEqual(self.history_count(), 1)

    def test_revocation_between_preflight_and_write_is_rejected_atomically(self):
        def interleave(name, arguments):
            if name == "publish_artifact":
                self.store.revoke("review-1")
            return mcp_call(self.store, name, arguments)

        outcome = run(self.install(interleave), self.arguments)
        self.assertEqual(outcome["status"], "REFUSED:target_error")
        self.assertEqual(self.history_count(), 0)

    def test_revocation_during_outage_prevents_recovery_write(self):
        call = self.install()
        with self.assertRaises(SimulatedCrash):
            call.gate.submit(call.proposal(self.arguments), crash_before_effect=True)
        self.store.revoke("review-1")
        self.assertEqual(run(self.install(), self.arguments)["status"], "REFUSED:target_error")
        self.assertEqual(self.history_count(), 0)

    def test_service_unavailable_before_dispatch_reports_not_sent(self):
        saved = self.store.path.with_suffix(".unavailable")
        self.store.path.rename(saved)
        outcome = run(self.install(), self.arguments)
        self.assertEqual(outcome["status"], "NOT_SENT")
        self.assertFalse(self.store.path.exists())

    def test_service_unavailable_during_recovery_preserves_unknown_outcome(self):
        call = self.install()
        proposal = call.proposal(self.arguments)
        with self.assertRaises(SimulatedCrash):
            call.gate.submit(proposal, crash_after_effect=True)
        saved = self.store.path.with_suffix(".unavailable")
        self.store.path.rename(saved)
        restarted = self.install()
        recovery = restarted.gate.recover()
        self.assertEqual(recovery[effect_id_for(proposal)], "UNRESOLVED:OperationalError")
        self.assertEqual(restarted.gate.journal.in_flight(), [effect_id_for(proposal)])
        self.assertFalse(self.store.path.exists())
        saved.rename(self.store.path)
        self.assertEqual(run(restarted, self.arguments)["status"], "COMMITTED_ON_QUERY")
        self.assertEqual(self.history_count(), 1)


@unittest.skipIf(os.name == "nt", "SIGKILL process-group tests require POSIX")
class ArtifactMcp(Fixture):
    def session(self, **kwargs):
        config = configuration(self.directory / "journal")
        config["claim_ttl"] = 0.2  # Test-only: workers are killed before recovery takes over.
        (self.directory / "config.json").write_text(json.dumps(config), encoding="utf-8")
        session = Session(
            str(self.directory),
            str(self.store.path),
            server=str(Path(__file__).parent / "support" / "artifact_mcp_server.py"),
            **kwargs,
        )
        self.addCleanup(lambda: session.kill() if session.proc.poll() is None else None)
        return session

    def publish(self, session, wait=True):
        return session.request(
            "tools/call", {"name": "publish_artifact", "arguments": self.arguments}, wait=wait
        )

    def wait_marker(self, marker):
        deadline = time.monotonic() + 10
        while not (self.directory / marker).exists():
            if time.monotonic() > deadline:
                self.fail(f"Server never reached {marker}")
            time.sleep(0.01)

    def test_mcp_lists_tools_and_publishes_with_receipt(self):
        session = self.session()
        names = {tool["name"] for tool in session.request("tools/list", {})["tools"]}
        self.assertEqual(names, set(tool_functions(self.store)))
        result = self.publish(session)
        self.assertNotIn("isError", result)
        self.assertEqual(result["structuredContent"]["version"], 1)
        self.assertEqual(result["_meta"]["interlock"]["status"], "COMMITTED")
        self.assertEqual(self.history_count(), 1)
        session.close()

    def test_kill_after_commit_then_newer_write_does_not_publish_again(self):
        session = self.session(slow=30)
        self.publish(session, wait=False)
        self.wait_marker("after-commit")
        session.kill()
        self.newer()
        time.sleep(0.25)
        restarted = self.session()
        result = self.publish(restarted)
        self.assertNotIn("isError", result)
        self.assertEqual(result["_meta"]["interlock"]["receipt"]["final"], "COMMITTED")
        self.assertEqual(self.store.get_artifact(self.arguments["name"])["version"], 2)
        self.assertEqual(self.history_count(), 2)
        restarted.close()

    def test_kill_before_commit_then_newer_write_refuses_stale_publication(self):
        session = self.session(slow_before=30)
        self.publish(session, wait=False)
        self.wait_marker("before-commit")
        session.kill()
        self.newer(version=0)
        time.sleep(0.25)
        restarted = self.session()
        result = self.publish(restarted)
        self.assertTrue(result.get("isError"), result)
        self.assertEqual(
            self.store.get_artifact(self.arguments["name"])["content"], "Newer reviewed report.\n"
        )
        self.assertEqual(self.history_count(), 1)
        restarted.close()


if __name__ == "__main__":
    unittest.main()
