# Validation record: foundation cleanup

Local validation on macOS, 2026-09-20, on branch `artifact-publication`. The validation baseline is upstream commit `822ec54692b30e1fdce04b55dfab62d0b56a60b2`. This record covers the artifact example, repository cleanup, and CLI improvements together.

## Results

| Check | Result |
| --- | --- |
| Untouched upstream baseline, Python 3.12.14 | 466 tests: 413 passed, 53 skipped. |
| Current suite, Python 3.12.14 | 491 tests: 438 passed, 53 skipped. |
| Current suite, Python 3.9.6 | 491 tests: 438 passed, 53 skipped. |
| Artifact workflow | All 22 tests passed, including process kills before/after commit. |
| CLI contracts | All 3 tests passed: help, malformed arguments, and receipt verification exit codes. |
| Ruff 0.15.21 | Lint and format checks passed in the maintained scope. |
| mypy 1.19.1 | Strict checks passed for all 6 artifact-example modules. |
| Recorded experiments | All 85 result files matched after regeneration, ignoring `Generated` timestamp lines. |
| Package smoke test | Wheel built, installed without dependencies into a temporary environment, and imported outside the source checkout. |
| Public entry points | Compatibility imports, both installed CLIs, and verification of the example receipt passed. |
| Original demo | Both `demo.py` and `examples.crash_recovery` passed modes `1`, `2`, `3`, and `naive`. |
| Working-tree checks | `git diff --check` passed; original license and generated evidence were not edited. |

The 53 skips comprise 43 PostgreSQL/runtime tests without the required database/Hypothesis setup and 10 tests needing optional SDKs. Those integrations were not validated. GitHub Actions, Linux, and Windows runs were not performed locally; the updated workflow will validate its configured matrix when run remotely. Static typing covers the artifact example, not the whole upstream library.

## Commands

```sh
uv run --no-project --python 3.12 python -m unittest discover -s tests -v
uv run --no-project --python /usr/bin/python3 python -m unittest discover -s tests -v
uv run --no-project --python 3.12 python -m unittest discover -s tests -p test_artifact_publication.py -v
uv run --no-project --python 3.12 python -m unittest discover -s tests -p test_cli.py -v
ruff check demo.py interlock examples tests/support tests/test_artifact_publication.py tests/test_mcp_proxy.py tests/test_site.py tests/test_cli.py
ruff format --check demo.py interlock examples tests/support tests/test_artifact_publication.py tests/test_mcp_proxy.py tests/test_site.py tests/test_cli.py
uvx --python 3.12 --from mypy==1.19.1 mypy
git diff --check
```

Here `/usr/bin/python3` resolved to Python 3.9.6. `UV_CACHE_DIR=/tmp/interlock-uv-cache` was set for uv commands. Reproduction commands for other environments are in the [contribution guide](../CONTRIBUTING.md).

In a disposable copy, `python experiments/run_all.py` and `python viewer/build.py` regenerated outputs for comparison with the source checkout. A separate disposable copy ran `uv build --wheel --out-dir <temporary wheels directory>`, then `uv venv` and `uv pip install --no-deps` for the produced wheel. Its installed `interlock-mcp --help`, `interlock-verify --help`, and `interlock-verify <example receipt>` completed successfully. No generated outputs were copied back.

## Issues found and resolved during cleanup

- Extracting the shared MCP client exposed an older test that mutated a global in another test module. Callers now import shared support and supply the desired server explicitly; the affected test and full suite passed afterward.
- The initial package smoke check found that `--help` exited with an error. Both CLIs now use `argparse`, with tests for help, usage errors, and verification exit codes.
- Windows CI exposed a scheduling-dependent expectation in the concurrent artifact test: a slower worker can safely refuse a stale premise after another worker commits. A deterministic interleaving test now covers that case and verifies that retry resolves to the single committed publication.
- Documentation link tests previously left files open. Those reads now use context managers.

This is a local engineering validation record. It does not establish a cloud deployment, improved benchmark performance, power-loss durability, or stronger guarantees for arbitrary remote destinations.
