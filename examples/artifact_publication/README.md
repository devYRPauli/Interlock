# Versioned artifact publication

A local reference workflow for publishing reviewed research reports through Interlock's existing MCP gate. An agent publishes a report, crashes before receiving the acknowledgement, and restarts after another operator has published a newer report. Recovery must identify the original publication without publishing twice or replacing the newer report.

This example extends [Interlock by Said Azaizah and Kiro Moussa](https://github.com/az-said/Interlock). The gate, approval envelopes, journal, MCP proxy, and receipt verifier are upstream work. The example adds a local artifact provider, MCP server, demo, and focused tests. The repository's original MIT license applies.

## Run the demo

From the repository root, with Python 3.9+ and no extra dependencies:

```sh
uv run --no-project --python 3.12 python -m examples.artifact_publication.demo
```

The demo leaves its files in a temporary directory and prints that directory. Use `--directory /absolute/path/to/new-directory` to choose a new location. It creates:

- `artifacts.sqlite`: provider state, immutable approvals, and publication history.
- `journal/`: Interlock's separate decision and recovery journal.
- `receipt.json`: the original publication's verifiable journal bundle.
- `interlock.json`: configuration for the MCP proxy.

Expected result: `COMMITTED_ON_QUERY`, current version `2`, and `receipt_valid: true`. The demo uses an explicitly **simulated** crash after commit. The subprocess tests below also kill a real proxy and its server before and after the transaction.

Verify the retained receipt independently, replacing the path with the printed directory:

```sh
uv run --no-project --python 3.12 python -m interlock.receipts /absolute/demo-directory/receipt.json
```

## Connect through MCP

Run the existing proxy from this repository's root, using the configuration and database created by the demo:

```sh
uv run --no-project --python 3.12 python -m interlock.mcp_proxy \
  --config /absolute/demo-directory/interlock.json -- \
  uv run --no-project --python 3.12 python -m examples.artifact_publication.mcp_server \
  --db /absolute/demo-directory/artifacts.sqlite
```

Use that command and working directory in your MCP client's stdio server configuration. The example implements the `2025-06-18` initialization handshake, tool listing, tool calls, and ping. It is a small example server, not a complete MCP SDK implementation.

The agent can call `get_artifact`, `get_approval`, `find_publication`, and `publish_artifact`. It cannot create or revoke approvals through MCP. To authorize a new publication, an operator runs the following locally against the provider (the demo's first two approvals are already used):

```python
import time
from examples.artifact_publication.storage import ArtifactStore

store = ArtifactStore("/absolute/demo-directory/artifacts.sqlite")
arguments = {
    "request_id": "research-003",
    "name": "reports/evaluation.md",
    "expected_version": 2,
    "content": "A third report reviewed by the operator.\n",
    "approval_id": "review-003",
}
store.approve(arguments, expires=time.time() + 3600)
# To revoke before publication: store.revoke("review-003")
```

Send `arguments` unchanged to `publish_artifact`. The proxy injects the operation `reference`. Reuse the exact arguments after an uncertain result; a changed report needs a fresh operator-approved request. `expected_version=0` means create only if absent. Names are logical database keys, not filesystem paths. The content remains in SQLite; this example does not upload a file to an external destination.

## What enforces correctness

Each publication uses one SQLite `BEGIN IMMEDIATE` transaction to:

1. Return a previous result for the same operation reference, rejecting a changed payload.
2. Prevent reuse of a published request ID under another operation reference.
3. Check the operator's exact approved request, expiry, and revocation status.
4. Compare the current version against the request's expected version.
5. Append the next artifact version and its SHA-256 digest to durable operation history.

This closes the gap between a gate's preflight check and the actual write. A competing publication or approval revocation immediately before the transaction is rejected by the provider. Revocation after commit cannot undo a historical publication.

`find_publication` queries historical operation references, not the current artifact's content. The proxy config selects lookup-based recovery (`dedupes: false`), while the provider also deduplicates transactionally as a second safeguard. A missing database or failed query raises an error rather than returning a fabricated negative lookup. Unexpected database failures terminate the example server so a potentially committed send stays unresolved in the proxy; restart it after restoring availability.

Interlock adds recorded decisions, approval checks, recovery orchestration, and receipts. A careful caller using this provider's atomic version checks and stable operation references can also preserve the publication invariant; a test explicitly covers that baseline. This example does not establish an advantage over such a caller, or a general exactly-once guarantee for arbitrary APIs.

## Validation and limits

```sh
uv run --no-project --python 3.12 python -m unittest discover -s tests -p test_artifact_publication.py -v
uv run --no-project --python 3.12 python -m unittest discover -s tests -v
```

Focused tests cover concurrent writers and gate instances, changed payloads, reused request IDs, expired/revoked approvals, changes between preflight and commit, missing storage, unavailable recovery reads, receipt verification, and real MCP process-group kills before/after commit. Process-kill tests require POSIX. No paid API, cloud credentials, or model calls are needed.

Local verification on Python 3.12.14, macOS, against upstream `822ec54692b30e1fdce04b55dfab62d0b56a60b2`:

- Untouched upstream: 466 tests, 413 passed, 53 skipped.
- With the artifact example and foundation cleanup: 490 tests, 437 passed, 53 skipped on Python 3.12.14 and 3.9.6; all 21 artifact tests passed.
- Skips: 43 PostgreSQL/runtime tests without `ILR_DSN`/Hypothesis and 10 optional SDK integration tests. These integrations were not validated.
- The demo returned `COMMITTED_ON_QUERY` with version 2 preserved; the independent `interlock.receipts` command reported `valid: true`.
- Ruff lint/format checks, strict example type checks, and `git diff --check` passed. See the [validation record](../../docs/validation.md) for exact commands, packaging checks, and limits.

Scope: one local machine, small text artifacts, trusted operator access to the database, and retained operation history. The MCP process has no authentication boundary from other programs running as the same OS user. SQLite lock acquisition orders competing writes and revocations. Neither power-loss behavior nor network-filesystem behavior is tested. Journal receipts attest to recorded checks; unsigned receipts do not prove that a privileged operator never rewrote the journal. No remote provider, retention policy, large-file streaming, or deployment is included.

The next integration should preserve the same atomic version, approval, and historical-lookup contract on a real destination, then compare it with a careful provider-native baseline under the same fault schedule.
