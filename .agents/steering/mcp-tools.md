---
inclusion: fileMatch
fileMatchPattern: "**/server.py, **/mcp/*.py"
---
# MCP Tool Patterns

## Registration

Bricks register tools, resources, and prompts in a framework-neutral
`ToolCatalog`. The native MCP 2.1.1 composer is the only transport surface.

```python
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from factory.mcp_utils.interface import deterministic, operational


def register(catalog: ToolCatalog) -> None:
    @catalog.tool()
    @deterministic(input_model=SearchInput, output_model=SearchOutput)
    def kb_search(query: str, limit: int = 10) -> ToolResult[SearchOutput]:
        return ok(SearchOutput(items=runtime.search(query, limit)))
```

The compatibility factory name `create_mcp_server()` may remain, but it returns
the same neutral catalog. It must not create another registry or transport.

## Tool Categories

- **`@deterministic`** — read-only; same input and state produce the same output.
- **`@operational`** — stateful and safe to retry under its idempotency contract.
- **`@authoring`** — changes configuration or executable policy; behavior-gated.

`@op_kind("shell" | "read" | "write" | "authoring")` is an orthogonal
routing trait. Categories describe effect; `op_kind` describes operational
modality. Unknown values fail at decoration time.

## Native MCP v2 Typed Pydantic Contracts

Every public tool MUST declare concrete same-brick Pydantic v2 `input_model`
and `output_model` DTOs. Input DTOs use `ConfigDict(extra="forbid",
strict=True)` or equivalent non-coercive constraints. The return annotation is
`ToolResult[OutputDTO]`; raw container annotations are not public contracts.

The native composer registers the category-decorated handler and its canonical
DTO metadata directly. Decoded flat arguments reach that handler unchanged
exactly once. The input DTO is the sole ingress authority and
`ToolResult[OutputDTO]` is the sole typed egress authority. Do not add SDK
coercion, default insertion, duplicate validation, duplicate serialization,
framework-specific signature adapters, alternate registries, or nested request
wrappers.

Typed egress is stable:

```json
{"schema_version":"v1","ok":true,"data":{},"error":null,"idempotency_key":null}
```

Consumers check `ok` before reading `data`. Domain-negative outcomes such as
`found: false` remain successful envelopes; transport or execution failures set
`ok: false`, `data: null`, and a typed `error`.

Resources and prompts are native MCP primitives rather than `ToolResult` tool
endpoints. Private helpers are not public MCP contracts.

## Wire and Idempotency Rules

Preserve every supported flat wire field and its `Field(...)` constraints on the
handler signature. A public input or output change requires an explicit
migration. Do not add `_v2` aliases or model-only `schema_version` inputs.

Keyed tools fingerprint canonical post-ingress input plus stable principal,
tenant, session, Workflow, run, and Agent identity when available. Reusing a key
for different input conflicts without provider execution; concurrent identical
calls single-flight. Process-local replay remains bounded. Workflow/storage owns
durable cross-process deduplication.

## Aggregator Contract

The `mcp_server` base composes one native MCP v2 surface from neutral catalogs.
Progressive and complete discovery read the same registry. `call_brick_tool`
preserves the invoked tool result or task payload without adding an incompatible
outer `ToolResult`; this is declared narrowly as `native_mcp_v2_transport_egress`.
It does not relax ordinary tool contracts.

Agent adapters receive only allowlisted descriptors and results from the shared
`ScopedCapabilityClientPort`. LangChain converts descriptors into private tool
objects; LangGraph execution remains bounded to one Workflow attempt. Neither
adapter opens a second MCP transport or imports another brick runtime.

## Naming

- Prefix domain tools with the brick name: `kb_search`, `workflow_start_run`.
- Use clear verbs: `get_`, `list_`, `create_`, `update_`, `delete_`, `start_`,
  `cancel_`.
- Contract tools remain `get_capabilities`, `health_check`, and
  `describe_config_schema`.
- Components reference tools by name, never by transport URL.

## Resources and Prompts

```python
@catalog.resource("kb://collections/{collection_id}")
def resource_collection(collection_id: str) -> str:
    return json.dumps(runtime.get_collection(collection_id))


@catalog.prompt()
def analyze_document(doc_id: str, question: str) -> str:
    return f"Analyze document {doc_id}: {question}"
```

## Polymorphic Parameters

Domain-agnostic list parameters use trinary semantics unless an explicitly
documented contract says otherwise:

| Value | Meaning |
|---|---|
| `None` | Back-compatible default behavior. |
| `[]` | Explicit strict-empty behavior. |
| Non-empty value | Caller-provided domain configuration. |

The intentional exception is `memory_retrieve(metadata={})`, which means no
metadata constraints and is equivalent to `None`; `tags=[]` still matches
nothing. When both filters are present, tags and metadata intersect.

Caller-provided Cypher labels, relationship types, and property keys MUST be
validated before query construction. Property keys use
`re.fullmatch(r"^[a-zA-Z_][a-zA-Z0-9_]*$", key)` at both contract and adapter
boundaries because property names cannot be parameterized.

## Domain-Neutral Examples

- Graph typed reads accept caller-provided `taxonomy_edges`; `None` keeps the
  compatibility default, `[]` performs no join, and a non-empty list defines
  the relationship, target label, and projected properties.
- Graph and Games count parameters follow the same `None`/`[]`/non-empty rule.
- `learning_compute_reward` returns authoritative signed reward fields in
  `ToolResult[ComputeRewardOutput]`; nested `raw` content is evidence only.
- `memory_retrieve` returns `ToolResult[MemoryRetrieveOutput]`; callers consume
  matches from `result.data.memories` after checking `result.ok`.

The identical Agent → Workflow → scoped native MCP v2 → Evals path must support
unrelated domains without domain-specific orchestration branches.
