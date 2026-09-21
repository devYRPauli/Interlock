# Interlock

**Recorded decisions and crash recovery for AI agent actions.**

[![Tests](https://github.com/az-said/Interlock/actions/workflows/test.yml/badge.svg)](https://github.com/az-said/Interlock/actions/workflows/test.yml) · Python 3.9+ · MIT · Standard-library core

Interlock sits between an agent and a tool that changes the world. It records the proposed action, checks its authority and assumptions, and keeps a journal that recovery can inspect after a crash. Each action has a receipt describing what was attempted, what was confirmed, and what remains uncertain.

Originally created by **Said Azaizah and Kiro Moussa**; the canonical project is [az-said/Interlock](https://github.com/az-said/Interlock). The repository includes a local artifact-publication workflow, integration guides, and recorded experiments. Original authorship, the MIT license, and historical evidence are preserved.

## Try it locally

```sh
git clone https://github.com/az-said/Interlock.git
cd Interlock
uv run --no-project --python 3.12 python demo.py 2
```

The original offline demo shows a side effect committed before a simulated crash, followed by recovery. It needs no credentials or external services. With a suitable Python already installed, `python demo.py 2` also works.

The artifact example exercises a concrete workflow: publish a reviewed report, lose the acknowledgement, and recover after another operator publishes a newer report.

```sh
uv run --no-project --python 3.12 python -m examples.artifact_publication.demo
```

It prints the retained database and receipt location. See the [artifact-publication guide](examples/artifact_publication/README.md) for MCP configuration, operator approvals, verification commands, and limits.

## Use the library

To install this checkout into a virtual environment:

```sh
uv venv --python 3.12
uv pip install --python .venv/bin/python -e .
```

On Windows, use `.venv/Scripts/python.exe` for the interpreter path. The core has no runtime dependencies; individual framework integrations and the separate PostgreSQL runtime have their own requirements.

| Integration | Entry point | Guide |
| --- | --- | --- |
| Python functions | `Interlock.effect(...)` | [Python API](docs/integrations.md) |
| In-process tool dictionaries | `interlock.tools.protect(...)` | [Tool integrations](docs/integrations.md) |
| MCP servers | `interlock-mcp --config config.json -- <server command>` | [MCP example](examples/artifact_publication/README.md) |
| Receipt verification | `interlock-verify receipt.json` | [Receipt implementation and contract](interlock/receipts.py) |
| Temporal, LangChain, Google ADK, AP2 | Framework-specific adapters | [Integration guide](docs/integrations.md) |

Register the same effect functions before calling `recover()` on restart. Keep request identities stable and preserve the journal directory. A new request ID or a fresh journal is not a recovery strategy.

## Guarantees and boundaries

Recovery depends on what the destination can prove:

| Destination capability | Recovery behavior |
| --- | --- |
| Deduplicates a stable operation ID | May retry within the provider's deduplication window, after required checks. |
| Can look up a historical operation ID | Queries the original effect and rechecks the recorded decision before a resend. |
| Neither capability | Records an ambiguous outcome rather than guessing whether a resend is safe. |

A preflight read cannot prevent the destination from changing immediately afterward. The destination must enforce relevant version or authorization constraints atomically with its write. The artifact example demonstrates this with a SQLite transaction.

Receipts describe recorded checks and outcomes. An unsigned hash chain provides internal consistency checks, not independent proof against an operator who can rewrite the journal. Claim expiry also depends on the provider's timing and retry semantics. This is not a universal exactly-once layer for arbitrary APIs.

A careful provider-native implementation can preserve the same effect invariant. The artifact example does not establish a performance or correctness advantage over that baseline. For measured upstream comparisons and known gaps, read the [evidence](docs/proof.md), [weakness audit](docs/11-weakness-audit.md), and [quality plan](docs/11-quality-plan.md). Those documents describe dated runs, not fresh validation of the current checkout.

## Repository guide

| Path | Responsibility |
| --- | --- |
| [`interlock/`](interlock/) | Installable gate, journals, approvals, receipts, adapters, and exporters. |
| [`examples/`](examples/README.md) | Small runnable reference integrations. |
| [`tests/`](tests/) | Regression and integration tests; shared helpers in `tests/support/`. |
| [`docs/`](docs/README.md) | Architecture, integration guides, evidence, and historical design notes. |
| [`runtime/`](runtime/) | Separately packaged PostgreSQL workflow runtime. |
| [`backend/`](backend/README.md), [`demo/`](demo/README.md) | Hosted-demo application and browser interface. |
| [`experiments/`](experiments/), [`scenarios/`](scenarios/) | Reproduction harnesses and scenario-specific adapters. |
| [`results/`](results/), [`viewer/`](viewer/) | Recorded experiment outputs and their viewer. |
| [`site/`](site/), [`infra/`](infra/) | Upstream landing site and deployment infrastructure. |
| [`research/`](research/), [`spec/`](spec/) | Research material and specification artifacts. |

The [architecture guide](docs/architecture.md) explains dependency boundaries and compatibility constraints. See [CONTRIBUTING.md](CONTRIBUTING.md) for formatting, linting, strict example type checks, and the test workflow.

## Validate changes

```sh
uv run --no-project --python 3.12 python -m unittest discover -s tests -v
```

The suite reports optional SDK and PostgreSQL tests as skipped when their dependencies or services are unavailable. A green offline run does not validate those integrations. [`tests/README.md`](tests/README.md) and [`results/`](results/) contain historical generated evidence; current command output is the source of truth for this checkout.

## Authors and license

- **Said Azaizah** — [GitHub](https://github.com/az-said) · [Website](https://said-azaizah.vercel.app)
- **Kiro Moussa** — [GitHub](https://github.com/kiromoussa) · [Website](https://kiro.city)

Originally built for Battle of the Coasts 2026, Cloud AI track, Boston. Further contributors are recorded in Git history. Distributed under the original [MIT license](LICENSE).
