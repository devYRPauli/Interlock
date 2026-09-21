# Documentation

Start with the [project README](../README.md) for usage and boundaries, then choose a guide by task.

## Build and integrate

| Guide | Use it for |
| --- | --- |
| [Architecture](architecture.md) | Package responsibilities, dependency boundaries, persistent identities. |
| [Contributing](../CONTRIBUTING.md) | Local checks, code conventions, and evidence handling. |
| [Validation record](validation.md) | Commands, results, skips, and limits for the foundation cleanup. |
| [Examples](../examples/README.md) | Runnable workflows with explicit limits. |
| [Integrations](integrations.md) | Python tools, MCP, Temporal, LangChain, ADK, and AP2. |
| [Recovery for repositories](repository-recovery.md) | Repository effect checks and recovery behavior. |
| [Runtime](07-runtime.md) | The separate PostgreSQL workflow runtime. |
| [Deployment](deploy.md) | Hosted demo operation and configuration. |

## Understand and evaluate

| Guide | Use it for |
| --- | --- |
| [How it works](how-it-works.md) | Original walkthrough of the gate and recovery model. |
| [Contract](02-contract.md) | Invariants and target capabilities. |
| [Evidence](proof.md) | Recorded experiments and their limitations. |
| [Scenarios](10-scenarios.md) | Scenario definitions and service-specific assumptions. |
| [Weakness audit](11-weakness-audit.md) | Known limitations and failure boundaries. |
| [Quality plan](11-quality-plan.md) | Upstream measurements and proposed follow-up work. |

## Historical material

The numbered research notes, [original narrative](00-the-whole-story.md), [pitch](08-pitch.md), [checkpoints](checkpoints/), and [research directory](../research/) preserve the upstream project's development context. Their dates, test counts, competitor comparisons, and plans are historical. Consult current code and fresh validation before treating them as current product behavior. Proposed work in those documents is not necessarily implemented.

The original [visual walkthrough](interlock-explained.html), [site](../site/), and generated [test report](../tests/README.md) remain available. Current onboarding and engineering conventions are maintained in the README, architecture guide, contribution guide, and example guides above.
