# Architecture and compatibility

Interlock coordinates decisions and recovery. The destination remains responsible for enforcing the write constraints it actually supports. Keep those responsibilities distinct when extending the system.

## Installable core

```text
interlock/
  __init__.py       Explicit top-level public exports
  easy.py           Interlock decorator API and function target adapter
  tools.py          Framework-neutral tool wrapping and outcomes
  mcp_proxy.py      MCP subprocess transport and routing
  gate.py           Dispatch and recovery decisions; comparison baselines
  journal.py        JSONL/SQLite journals, claims, effect IDs, hash chains
  approvals.py      Approval envelopes, authority, review inbox, routing
  leases.py         Basic lease store
  escalation.py    Shared refusal and escalation descriptions
  receipts.py      Receipt construction and verification
  confirm.py       Reconciliation with later provider confirmations
  targets/         Repository and payment targets
  integrations/    ADK and AP2 adapters
  export/          Audit destination adapters
  temporal.py      Temporal activity helper
  langchain_tools.py  LangChain adapter
  scoreboard.py    Experimental trace scoring
```

The standard-library core is a separate distribution from `runtime/interlock_runtime`, which adds PostgreSQL workflow execution. The demo backend, research harnesses, and examples are not installed as part of `interlock-gate`.

The dependency direction is from integration code toward gate, journal, and receipt behavior. A new provider belongs in an adapter or example, not inside the generic recovery state machine. Avoid adding SDK dependencies to the base package merely to support one integration.

## Artifact reference workflow

```text
examples/artifact_publication/
  models.py         Typed publication request, validation, domain rejection
  storage.py        SQLite transactions and durable publication history
  configuration.py  Interlock gate configuration
  mcp_server.py     Tool exposure, MCP result envelopes, stdio transport
  demo.py           Reproducible crash/recovery workflow
  README.md         Setup, use, verification, and limitations
```

Storage has no dependency on the MCP transport or Interlock. It checks request identity, the immutable operator approval, and the destination version within the same write transaction. It raises `PublicationRejected` only for a definite rejection. The MCP layer translates that exception to `isError`; unexpected storage failures remain distinguishable from a confirmed rejection.

The agent can publish and inspect state but cannot mint approvals through the tool list. Historical lookup is keyed by the original operation reference, even after a later publication replaces the current version. The storage database and Interlock journal remain separate so tests can compare the receipt with destination state.

## Persistent compatibility

These are behavioral contracts, not formatting choices:

- Keep existing `interlock` imports, CLI entry points, effect IDs, journal filenames, and serialized journal fields stable unless a migration is part of the change.
- `Interlock.effect` derives journal names from the decorated function's module and qualified name. Tool adapters also supply module names. Moving or renaming those functions can strand recovery history.
- Register effects before startup recovery. Preserve the original recorded payload while settling an uncertain send; a newly generated payload is a separate decision.
- A lookup error must not become `found: false`. A timeout or disconnected server must not be treated as proof that nothing happened.
- An expiring worker claim does not itself prove a remote operation stopped. Respect target timeouts, deduplication windows, and atomic preconditions.
- A stored preflight check is not an atomic destination-side constraint. Use compare-and-set or an equivalent provider primitive when the invariant requires it.

The existing `easy.py`, `temporal.py`, and `langchain_tools.py` paths remain stable even though some adapters also live under `integrations/`. Compatibility is more valuable here than directory symmetry. Legacy re-exports from `mcp_proxy.py` are explicit and retained.

## Tests and evidence

Tests stay discoverable through `python -m unittest discover -s tests`. Shared process lifecycle utilities and test-only crash barriers live in `tests/support/`. Recovery tests should assert both the actual publication history and the recorded outcome.

The [contribution guide](../CONTRIBUTING.md) defines enforced quality scopes. The remaining historical experiments and service-dependent integrations have separate validation requirements. Generated evidence is preserved rather than relabeled as current after a formatting or structural change.
