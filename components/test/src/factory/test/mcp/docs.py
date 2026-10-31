"""Documentation content for Test MCP resources."""

TEST_DOCS = {
    "overview": {
        "title": "Test Brick Overview",
        "content": """# Test Brick

Trusted-local test execution and JUnit debt comparison for the Python Factory.

## Public MCP contract

All 14 tools use flat kwargs, strict same-brick Pydantic v2 ingress, and a
`ToolResult[OutputDTO]` v1 envelope. Unknown fields and coercive values are
rejected before the runtime is called.

| Tool | Input fields and defaults | Output DTO |
|---|---|---|
| `test_get_capabilities`, `test_health_check`, `test_describe_config_schema`, `test_list_files` | none | `CapabilitiesOutput`, `HealthOutput`, `ConfigSchemaOutput`, `ListFilesOutput` |
| `test_discover` | `path="."`, `pattern="test_*.py"` when omitted; an omitted pattern uses the runtime-authored default, while an explicit pattern wins | `DiscoveryOutput` |
| `test_compare_junit` | required `base_report`, `candidate_report` | `JunitCompareOutput` |
| `test_run_all` | `verbose=False` when explicit; an omitted value uses the runtime-authored verbose default | `ExecutionOutput` |
| `test_run_component` | required `component_name`; an omitted `verbose` uses the runtime-authored default | `ExecutionOutput` |
| `test_run_path` | required `path`; an omitted `pattern`/`verbose` uses runtime-authored defaults, while explicit values win | `ExecutionOutput` |
| `test_authoring_get_status` | none | `AuthoringStatusOutput` |
| `test_authoring_set_adapter` | required `adapter` | `MutationOutput` |
| `test_authoring_set_timeout` | required `timeout_seconds` | `MutationOutput` |
| `test_authoring_set_pattern` | required `pattern` | `MutationOutput` |
| `test_authoring_set_verbose` | required `verbose` | `MutationOutput` |

The callable defaults shown in the table are the wire-level defaults. Because the
raw-kwargs transport preserves omitted-field presence, `test_discover` and
`test_run_path` resolve an omitted `pattern` from the runtime's authored default,
and execution tools resolve an omitted `verbose` from the authored default.
Explicit values always override those runtime defaults.

The envelope contains `schema_version`, `ok`, `data`, `error`, and
`idempotency_key`. Output lists are bounded; truncation flags identify omitted
entries. MCP paths are workspace-relative and sensitive credentials, paths,
JUnit identities, and diagnostics are redacted.

## Direct API versus MCP boundary

`TestRuntime` and `compare_junit` are trusted-local CI APIs. They retain their
normal local path behavior and are not network-safe. `McpTestRuntime` is the
MCP-only facade: it validates workspace-relative paths, rejects symlinks and
non-regular reports, bounds execution and XML resources, and projects a safe
response. Do not expose the direct runtime as an MCP endpoint.

JUnit reports are limited to 5 MiB, 20,000 testcases, 100,000 XML elements,
64 levels of nesting, and bounded text/attribute values. Pytest subprocesses
use argv execution, process-group cleanup, timeout limits, and bounded output.

## Native MCP v2 transport note

The neutral `ToolCatalog` retains each category-decorated handler and its strict
Pydantic input/output DTO metadata. Native MCP v2 dispatch passes decoded flat
arguments to that handler exactly once, preserving wire types and omitted-field
presence without a second framework validation or serialization layer.

## Quick start

```text
test_run_all()
test_run_component(component_name="auth")
test_discover(path="components/auth/test")
```

## Adapters

- `pytest` - real pytest execution (default)
- `memory` - in-memory mock for testing the Test brick

## Tool categories

- Deterministic: capabilities, health, schema, discovery, JUnit comparison
- Operational: all-test, component, path, and file-list execution
- Authoring: runtime-local adapter, timeout, pattern, and verbose defaults
""",
    },
    "adapters": {
        "title": "Test Adapters",
        "content": """# Test Adapters

The Test brick uses a ports/adapters architecture.

## PytestAdapter

The default adapter executes `pytest` through argv-only subprocesses. Output is
drained with a fixed bound, and timeout cleanup kills the child process group.

```python
from factory.test.runtime import PytestAdapter

adapter = PytestAdapter(root_dir=".")
result = adapter.run_tests("components/auth/test")
```

## MemoryAdapter

Use the in-memory adapter for deterministic unit tests:

```python
from factory.test.runtime import MemoryAdapter, MockTestCase

adapter = MemoryAdapter()
adapter.add_test_case(MockTestCase(name="test_example", file="test_example.py", status="passed"))
result = adapter.run_tests(".")
```

Both adapters implement `TestRunner` with `run_tests`, `discover_tests`, and
`health_check`.
""",
    },
    "testing-guide": {
        "title": "Testing Guide",
        "content": """# Testing Guide

Use the standard component layout:

```text
components/<name>/test/factory/<name>/test_core.py
```

Test files use `test_*.py`; test functions use `test_*`; test classes use
`Test*`. Run one component with `test_run_component`, a contained path with
`test_run_path`, or the workspace with `test_run_all`.

For failures, first run the same contained path with `verbose=True`, inspect
the bounded redacted output, then use the `debug_failure` prompt. Keep tests
focused, mock slow dependencies, and run `foreman_guardian_check` before a
change is committed.
""",
    },
}
