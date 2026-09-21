# Contributing

Interlock handles uncertain side effects. A contribution should make the behavior easier to inspect and preserve the difference between a confirmed effect, a definite rejection, and an unknown outcome.

## Local setup

Use Python 3.9+ for the core. These commands select Python 3.12 for a consistent development environment and use isolated tooling without changing the runtime dependencies or creating a project lockfile.

```sh
uv run --no-project --python 3.12 python -m unittest discover -s tests -v
uvx --from ruff==0.15.21 ruff check demo.py interlock examples tests/support tests/test_artifact_publication.py tests/test_mcp_proxy.py tests/test_site.py tests/test_cli.py
uvx --from ruff==0.15.21 ruff format --check demo.py interlock examples tests/support tests/test_artifact_publication.py tests/test_mcp_proxy.py tests/test_site.py tests/test_cli.py
uvx --python 3.12 --from mypy==1.19.1 mypy
git diff --check
```

Ruff configuration lives in `pyproject.toml`: 100-character lines, Python 3.9 syntax, import sorting, and the selected error rules. Replace `format --check` with `format` to apply formatting within that scope.

Formatting and linting currently cover the complete installable core, runnable examples, shared test infrastructure, and the maintained MCP/documentation tests listed above. Historical experiments, the separate runtime, and the remaining regression files have not been reformatted. When maintaining another area, expand the enforced scope in the same change after checking its baseline; do not hide findings with broad ignores.

Strict mypy checking covers `examples/artifact_publication`. The existing `interlock` library is an explicitly untyped dependency at that boundary; JSON and SQLite row shapes use `Any` where data enters dynamically. Passing this check does not mean the whole library has static type coverage.

The GitHub workflow runs the same quality checks, the test suite on Linux/Python 3.9, 3.12, and 3.13, and Windows/Python 3.13. Workflow execution is separate from a local test run.

## Focused verification

For the artifact workflow:

```sh
uv run --no-project --python 3.12 python -m unittest discover -s tests -p test_artifact_publication.py -v
uv run --no-project --python 3.12 python -m examples.artifact_publication.demo
```

Use the existing fault and race tests when changing dispatch, recovery, leases, or storage. A useful test asserts the destination state as well as the receipt; a reported success without the intended side effect is a failure. Cover changed facts, lost acknowledgements, concurrent workers, and failed lookups when those paths are affected.

The default suite skips optional framework SDKs and the PostgreSQL tests unless their requirements are available. See the [runtime guide](docs/07-runtime.md) for runtime setup and [backend guide](backend/README.md) for the service-backed demo. Report skips and missing services explicitly. Live experiments can create remote resources and incur cost; inspect their instructions and obtain appropriate authorization before running them.

## Structure and naming

- Put reusable gate behavior in `interlock/`; keep provider-specific constraints in adapters.
- Put a self-contained reference workflow under `examples/<workflow>/` with its own README.
- Name modules for their responsibility: `models.py`, `storage.py`, `configuration.py`, and `mcp_server.py` in the artifact example.
- Keep shared test clients and fault-injection servers under `tests/support/`. Test modules should not import helper classes from another test module.
- Prefer small cohesive functions, explicit exceptions, and named public exports. Preserve established imports and command entry points when reorganizing an existing API.
- Keep example output in temporary directories or an explicitly chosen data directory, outside source files.

Read the [architecture guide](docs/architecture.md) before changing boundaries. Existing core module names are compatibility surfaces: renaming an effect function or changing its module can change which persisted journal a restarted process opens.

## Evidence and documentation

`results/`, built viewers, and `tests/README.md` contain generated evidence. Do not hand-edit their numbers. Generators such as `experiments/run_all.py`, `viewer/build.py`, and `tests/report.py` write files; use a disposable checkout when only checking reproducibility. Keep dated research clearly separated from current validation.

For a change, record its scope, commands run, outcomes, skips, and remaining limits. If altering a compatibility contract, include migration instructions and a test against the old call path. Preserve original author attribution and the MIT license when publishing a derivative example or fork.
