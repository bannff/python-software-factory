---
inclusion: fileMatch
fileMatchPattern: "components/**/*, bases/**/*"
---
# Brick Anatomy

The normative ownership boundaries live in [`.agents/steering/factory-protocol.md`](../../.agents/steering/factory-protocol.md). This file defines structural patterns only.

All bricks (components AND bases) follow the same polymorphic, adapter-based pattern. Workflow is the structural exemplar; that does not make it the owner of intelligent research, synthesis, or within-attempt Agent Graph work.

## Directory Structure (Exemplar: workflow)

```
components/<name>/
├── BRICK.yaml                    # Metadata (required)
├── src/factory/<name>/
│   ├── __init__.py
│   ├── interface.py              # Public API: create_server + Runtime
│   ├── server.py                 # MCP server factory (~50 LOC, delegates to mcp/)
│   ├── core.py                   # Shared types/constants
│   ├── authoring.py              # Authoring mode manager
│   ├── runtime/                  # Business logic (polymorphic)
│   │   ├── __init__.py
│   │   ├── ports.py              # Protocol interfaces (REQUIRED)
│   │   ├── runtime.py            # Main runtime class
│   │   ├── models.py             # Pydantic models
│   │   └── adapters/             # Backend implementations
│   │       ├── memory.py
│   │       └── <backend>.py
│   ├── mcp/                      # Full MCP primitives (REQUIRED)
│   │   ├── __init__.py
│   │   ├── deterministic.py      # Contract tools + read-only queries
│   │   ├── operational.py        # Stateful operations
│   │   ├── authoring.py          # Security-gated config changes
│   │   ├── resources.py          # Schemas, docs, live data
│   │   ├── prompts.py            # Guided workflows
│   │   ├── docs.py               # Documentation content
│   │   └── templates.py          # Prompt templates
│   └── adapters/                 # Optional — private SDK adapters,
│                                 # e.g. LangChain agents and bounded LangGraph
│                                 # execution. SDK objects never cross the brick
│                                 # boundary; capabilities arrive through the
│                                 # shared scoped native MCP v2 client.
└── test/factory/<name>/
    └── test_*.py
```

## BRICK.yaml Schema

```yaml
name: <brick_name>
type: component | base
namespace: factory.<brick_name>
description: One-line description
mcp_enabled: true
features:
  - feature_tag_1
adapters:
  - memory
  - <backend>
mcp_resources:
  - <name>://schemas/*
  - <name>://docs/*
mcp_prompts:
  - create_<thing>
  - debug_<thing>
```

## interface.py Pattern

```python
"""Polylith Interface for <name> module."""
from .server import create_mcp_server as create_server
from .runtime.runtime import <Name>Runtime as Runtime
```

When a brick exposes a "give me a runtime with sensible defaults" factory for cross-brick contract tests or quick-start usage, the canonical export name is `default_runtime` — a zero-arg callable that returns a fully-wired `Runtime` with default in-memory adapters. Exposing it on the public interface lets other bricks acquire a real runtime via `factory.<name>.interface.default_runtime()` without violating the no-cross-imports rule. The metrics brick is the reference example.

## server.py Pattern (Modular)

```python
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from factory.<name>.mcp import deterministic, operational, authoring
from factory.<name>.mcp import register_resources, register_prompts

def create_tool_catalog(runtime: <Name>Runtime) -> ToolCatalog:
    catalog = ToolCatalog("<name>-brick")

    deterministic.register(catalog, runtime)
    operational.register(catalog, runtime)
    authoring.register(catalog, runtime, manager)
    register_resources(catalog, runtime)
    register_prompts(catalog, runtime)
    return catalog

# Compatibility factory name; returns the same neutral catalog.
create_mcp_server = create_tool_catalog
```

## runtime/ports.py Pattern (Polymorphic)

```python
from typing import Protocol, Any

class <Name>Storage(Protocol):
    def health_check(self) -> dict[str, Any]: ...
    def save(self, key: str, data: Any) -> None: ...
    def load(self, key: str) -> Any | None: ...
```

### AWS Adapter Pattern (Optional)

When a brick needs multiple AWS service backends (e.g., DynamoDB + ElastiCache for cache), use a single `aws.py` adapter with a `service` selector that delegates to backend classes in a `backends/` subfolder:

```
runtime/adapters/
├── memory.py
├── redis.py
├── aws.py              # Entry point — service selector + delegation
└── backends/
    ├── dynamodb.py     # One backend per AWS service
    └── elasticache.py
```

```python
# runtime/adapters/aws.py
class AWSCacheAdapter:
    def __init__(self, service: str = "dynamodb", **config):
        match service:
            case "dynamodb":
                from .backends.dynamodb import DynamoDBBackend
                self._backend = DynamoDBBackend(**config)
            case "elasticache":
                from .backends.elasticache import ElastiCacheBackend
                self._backend = ElastiCacheBackend(**config)

    def infrastructure_spec(self) -> dict[str, Any]:
        """Return AWS resource requirements — every AWS adapter must expose this."""
        return self._backend.infrastructure_spec()
```

For single-service AWS adapters (e.g., graph → Neptune), the `backends/` subfolder is unnecessary — implement directly in `aws.py`.

### Domain Subpackage Pattern (Optional)

When a brick has shared business logic consumed by multiple adapters (e.g., a system prompt and tool selection used by both a local and AWS adapter), extract it into a domain subpackage under `runtime/`:

```
runtime/
├── ports.py
├── chat.py                 # Singleton accessor
├── companion/              # Domain subpackage — shared WHAT
│   ├── __init__.py
│   ├── prompt.py           # System prompt
│   └── tools.py            # Semantic tool selection
└── adapters/               # Adapter implementations — the HOW
    ├── langchain_agent.py # Uses companion/ prompt + scoped MCP capabilities
    └── memory.py          # Test mock
```

The subpackage handles shared registry-driven runtime support (prompt content and capability filtering). Adapters handle the HOW (LangChain, LangGraph, AWS, mock). Keep domain intelligence in registered personas and skills rather than hard-coded subpackage logic; the Agent brick's `companion/` subpackage is a current implementation example, not a second orchestration authority.

## MCP Primitives (REQUIRED for all bricks)

Every MCP-enabled brick MUST have full `mcp/` subpackage:

- **deterministic.py**: Contract tools (get_capabilities, health_check, describe_config_schema) + read-only queries
- **operational.py**: Stateful but idempotent operations
- **authoring.py**: Security-gated configuration changes
- **resources.py**: `@mcp.resource("brick://...")` for schemas, docs, live data
- **prompts.py**: `@mcp.prompt()` for guided workflows

See `components/workflow/` as the canonical exemplar.

## Brick-Declared Views (Optional)

Bricks with a UI surface declare views as **data** via a `mcp/views.py` module.
The dashboard discovers and renders these automatically — no dashboard code changes needed.

### mcp/views.py Pattern — Page Skeleton (3-zone layout)

All views use the standardized `page` component type which renders a 3-zone layout:
- Zone 1 (hero): gradient banner with icon, title, subtitle, tooltip
- Zone 2 (info + controls): metrics on the left, form on the right
- Zone 3 (output): tables, tabs, charts, cards — everything else

Children declare their zone via `"zone": "info"` or `"zone": "controls"` in props.
Children without a zone go to the output area.

```python
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from factory.mcp_utils.interface import deterministic

def register(catalog: ToolCatalog) -> None:
    @catalog.tool()
    @deterministic
    def <brick>_get_views() -> list[dict[str, Any]]:
        """Return UIView definitions for the <Brick> brick."""
        return [{
            "id": "<brick>-<view>",
            "name": "Human-Readable Name",
            "brick": "<brick>",
            "icon": "🔍",
            "layout": {"type": "flex", "direction": "column"},
            "components": [{
                "id": "<brick>-page",
                "type": "page",
                "props": {
                    "title": "Page Title",
                    "subtitle": "Description of what this view does",
                    "icon": "🔍",
                    "gradient": "from-blue-500 to-cyan-500",
                    "tooltip": "Hover hint for the page",
                },
                "children": [
                    {
                        "id": "<brick>-stat",
                        "type": "metric",
                        "props": {
                            "zone": "info", "label": "Items",
                            "value": "—", "icon": "document",
                            "tooltip": "Metric tooltip text",
                        },
                    },
                    {
                        "id": "<brick>-form",
                        "type": "form",
                        "props": {
                            "zone": "controls",
                            "tool": "<brick>_<tool_name>",
                            "submit_label": "Submit",
                            "fields": [
                                {"name": "query", "label": "Query", "type": "text",
                                 "placeholder": "Search...", "tooltip": "Help text"},
                                {"name": "mode", "label": "Mode", "type": "select",
                                 "options": [{"value": "a", "label": "A"}]},
                                {"name": "limit", "label": "Limit", "type": "range",
                                 "min": 1, "max": 50, "value": 10},
                                {"name": "payload", "label": "Payload", "type": "textarea",
                                 "placeholder": "{}"},
                            ],
                        },
                    },
                    {
                        "id": "<brick>-results",
                        "type": "table",
                        "props": {
                            "columns": [{"key": "id", "label": "ID"}],
                            "rows": [],
                        },
                    },
                ],
            }],
            "metadata": {
                "description": "What this view does",
                "nav_label": "Nav Label",
                "nav_order": 10,
            },
        }]
```

### Key rules

- Components reference tools by **name** (`"tool": "kb_search"`), never by URL
- The rendering adapter resolves tool names to transport-appropriate actions
- Form field types: `text`, `number`, `select`, `textarea`, `range` — all support `tooltip`
- Metric `icon` prop accepts legacy aliases (`chart`, `list`, `document`, `users`, `default`) or any [Heroicons](https://heroicons.com/) name (`shield-check`, `globe-alt`, `cpu-chip`, etc.) — 324 outline icons available via the ui brick's `heroicons` registry
- Supported component types: `page`, `text`, `form`, `table`, `metric`, `button`, `card`, `list`, `chart`, `alert`, `progress`, `image`, `hero`, `tabs`, `breadcrumbs`, `modal`, `toast`, `graph_viewer`, `chat`
- Views are registered in the ui brick's ViewManager at dashboard startup
- The dashboard renders views via `render_view(view_id, adapter="htmx")`
- The dashboard exposes GET and POST handlers at `/api/tools/{tool_name}` (forms use POST, lazy-load tabs use GET) and POST at `/api/chat/{tool_name}` for chat components
- HTML form values are auto-coerced from strings to int/float/JSON by the dashboard bridge

### Rendering pipeline

```
Brick (*_get_views)  →  Bridge (collect_views)  →  ui ViewManager  →  HTMXAdapter  →  Dashboard shell
                                                                    →  ReactAdapter →  Companion X
```

The FletAdapter outputs real `ft.Control` instances (content type `application/x-flet-control`), enabling native Flet rendering on web, desktop, and mobile. Native flet-charts (BarChart, LineChart, PieChart, ScatterChart) and a Canvas + InteractiveViewer graph viewer are supported.

### Aggregator tool name format

The MCP aggregator prefixes tool names as `{brick_name}_{original_tool_name}`.
For tools registered with explicit `name=` like `name="security.analyze"`, the
aggregated name becomes `security_security.analyze`. Reference the aggregated
name in view form `tool` props.

### Current bricks with views (21 views across 15 bricks)

| Brick | Views |
|-------|-------|
| agent | agent-chat, agent-launch, agent-registry |
| auth | auth-manager |
| cache | cache-dashboard |
| evals | evals-dashboard, evals-suites |
| events | events-stream |
| games | games-play |
| graph | graph-explorer, graph-stats, graph-manage |
| integrations | integrations-dashboard |
| kb | kb-search |
| memory | memory-browser |
| metrics | metrics-dashboard |
| security | security-dashboard |
| storage | storage-browser |
| telemetry | telemetry-dashboard |
| workflow | workflow-dashboard |

Any brick can add views by creating `mcp/views.py` and registering it in `server.py`.

## Agent Registration and Evidence-Promoted Templates

Agent registrations are JSON-serializable data: persona, skills, scoped model/capability access, structured-output contract, and bounded execution policy. At runtime, the control-plane runtime asks the Agent brick to compose the smallest objective-specific LangChain agent or bounded LangGraph from those registrations. This adaptive within-attempt composition does not transfer durable lifecycle ownership from Workflow.

Keep the permanent template catalog small. Promote a Graph topology only when repeated evaluation evidence shows that it is stable, reusable, and safer than runtime composition; otherwise retain the learned behavior in persona/skill/SOP data. Registrations contain no embedded callables or import-time side effects.

Do not add bespoke task factories, executor kinds, or result-shape shims merely to freeze a team topology. Use native SDK composition for Agent work, MCP for typed capability handoffs, and Workflow for durable attempts, global budgets, retries, cancellation, recovery, stopping, and terminal reasons. If an SDK primitive is genuinely missing, document the exact source/version gap and upstream issue as required by `dev-principles.md`.

