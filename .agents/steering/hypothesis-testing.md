# Hypothesis Property-Based Testing Guide

This guide covers how to write and maintain Hypothesis property-based tests in this repo. Reference it when writing or updating tests for any stateful brick.

## When Hypothesis Is Required

Every brick with stateful operations (CRUD stores, state machines, data transformations) MUST have a `test_*_properties.py` file. Bricks that are pure pass-through or config-only (http, logger, mcp_utils) may skip this.

## Canonical Exemplar

`components/agent/test/factory/agent/test_job_manager_stateful.py` — follow its structure, patterns, and style.

## File Conventions

- File name: `test_<adapter>_properties.py` in the brick's `test/` directory
- Must stay under 200 LOC (repo tenet)
- Module docstring explaining what's being tested and which properties are verified
- Use `hypothesis.settings(max_examples=50)` to keep tests fast

## Test Patterns

### @given for stateless properties
Use `@given` with strategies to fuzz inputs and verify single-operation invariants:
- Store-then-retrieve roundtrips
- Delete semantics (returns True if existed, False if not)
- Filter/list correctness
- Idempotent operations (last write wins)
- Edge cases: empty inputs, boundary values

### RuleBasedStateMachine for stateful sequences
Use for bricks with multiple interacting operations (CRUD stores, game engines, workflow managers):
- Track expected state in a `model` dict alongside the real adapter
- Use `@rule` for each operation (create, read, update, delete)
- Use `@invariant` to assert model and adapter stay in sync after every step
- Use `@initialize` to reset both model and adapter

### Async adapters
For async bricks (sandbox, notification, events), use a `_run_async` helper:
```python
def _run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is None:
        return asyncio.run(coro)
    return loop.run_until_complete(coro)
```

### Filesystem-backed adapters
For bricks that use the filesystem (kb, storage), use `tempfile.mkdtemp()` inside each test body for isolation. Don't mix pytest `tmp_path` fixtures with `@given`.


## Strategy Guidelines

- IDs/keys: `st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N")))`
- Content: `st.text(min_size=0, max_size=200)`
- Binary data: `st.binary(min_size=0, max_size=1000)`
- Enums/choices: `st.sampled_from([...])` for known value sets
- Optional fields: `st.one_of(st.none(), <strategy>)`
- Composite objects: `@st.composite` or `st.builds(ModelClass, ...)`

## Existing Property Test Files

These files already exist and should be updated (not recreated) when their brick's adapter changes:

| Brick | Test File |
|-------|----------|
| agent | `test_job_manager_stateful.py` (exemplar) |
| cache | `test_memory_properties.py` |
| workflow | `test_storage_properties.py` |
| events | `test_memory_properties.py` |
| storage | `test_blob_local_properties.py` |
| graph | `test_networkx_properties.py` |
| memory | `test_memory_properties.py`, `test_amem_properties.py`, `test_neo4j_graph_properties.py` |
| permissions | `test_evaluator_properties.py` |
| kb | `test_kb_runtime_properties.py`, `test_neo4j_vector_properties.py`, `test_entity_extraction_properties.py`, `test_bm25_properties.py`, `test_authoring_properties.py` |
| notification | `test_stdio_properties.py` |
| games | `test_connect_four_properties.py` |
| sandbox | `test_mock_adapter_properties.py` |

## PR Safety Test Gates

The core PR gate checks out immutable base (`github.event.pull_request.base.sha`) and candidate (`github.sha`) trees and runs each with its own frozen lock. It compares validated JUnit reports by pytest identity: `file + classname + name` (including parameter IDs), with `setup`, `call`, `teardown`, or `collection` phase included in the debt key. Aggregate failure counts never offset one another.

The identity ratchet behaves as follows:

- A candidate failure or error absent at base blocks; `failure → error` also blocks.
- Unchanged debt and `error → failure` remain visible as legacy debt.
- Baseline debt resolves only when the same identity executes and passes. Collection debt has one narrow equivalent: the same file collects and every emitted case passes.
- Missing, skipped, xfailed, or otherwise non-passing baseline debt blocks; deleting or suppressing a test is not a fix.
- Collection failures or errors in either report, malformed/empty/incomplete/ambiguous reports, dependency-sync/runner/timeout failures, and pytest exit codes above 1 fail closed. Exit 1 is accepted only long enough to compare debt; the comparator itself remains required and blocking.

### Strict lane ownership

Core excludes `components/dataset/test` and `components/machine_learning/test` completely. Those paths are wholly owned by required strict lanes:

| Lane | Owned path | Strict coverage |
|------|------------|-----------------|
| CAN | `components/dataset/test` | Preflight `asammdf` and `cantools`, then run all Dataset tests |
| ML | `components/machine_learning/test` | Preflight every declared ML backend, then run all Machine Learning tests |
| MLX | Native MLX acceptance on macOS arm64 | Preflight the platform and native passport dependencies, then run `test_mlx_timeseries.py` and `test_mlx_passport_strict.py` |

Optional-backend test modules use `pytest.importorskip` so ordinary default-dependency/core development can proceed without every extra. That skip behavior is not strict-lane evidence: CI preflights each lane's required backends before pytest, so a missing dependency fails instead of silently reducing coverage.

Use the matching local environment before running a lane:

```bash
uv sync
uv sync --group can-test
uv sync --group ml
uv sync --group mlx-test
```

These are local setup commands. CI uses the corresponding `uv sync --frozen` form to enforce each revision's lock.

## Hard Rules

- Use ONLY public APIs in assertions — never access `_private` attributes
- No cross-brick imports — each test file imports only from its own brick
- Tests must be independent — no shared mutable state between test functions
- All tests must pass when run with `pytest <test_file> -v`