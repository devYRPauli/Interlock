# Runnable examples

Examples demonstrate a bounded workflow and document its assumptions. They use the existing library without adding dependencies to the installable core.

| Example | Demonstrates | Requirements |
| --- | --- | --- |
| [Artifact publication](artifact_publication/README.md) | Atomic version checks, operator approvals, MCP, and recovery after a lost acknowledgement. | Python 3.9+, local SQLite, no credentials. |
| [Original crash demo](crash_recovery.py) | Recovery across the three target capability tiers. | Python 3.9+, no credentials. |
| [Browser demo](../demo/README.md) | Hosted-demo application and optional live service execution. | See its guide; live mode requires external services. |

Run examples from the repository root. Their databases, journals, and receipts belong in temporary or explicitly selected data directories, not beside the source. Use `tests/support/` for test-only fault injection rather than exposing crash controls as production tool arguments.

The root `demo.py` remains a compatibility entry point for `examples.crash_recovery`. Both commands run the same workflow.
