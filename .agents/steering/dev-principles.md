# Dev Principles

These are implementation principles for this workspace. The single normative architecture and control-plane authority is [`.agents/steering/factory-protocol.md`](../../.agents/steering/factory-protocol.md). This file explains how to implement that doctrine; repository-development orchestration below does not redefine runtime ownership.

## Architectural Principles

- **MCP-First**: Every brick exposes and consumes deterministic capabilities through MCP, never through another brick's internals. A capability brick may invoke another brick only for a typed, bounded operation; it must not grow adaptive planning or cross-brick lifecycle ownership. Adaptive composition belongs to registered Agent Graph/Swarm surfaces, while Workflow owns durable cross-brick attempts, budgets, retries, cancellation, recovery, and stopping.
- **SDK-First**: When a brick wraps a third-party SDK as its adapter (Strands, Bedrock, FastMCP, etc.), use the SDK's native primitives — plugins, hooks, registries, lifecycle events, sessions, conversation managers. Reimplementing what the SDK provides is a tenet violation. The brick's MCP surface is the polymorphic boundary; the internal implementation should leverage the SDK fully. If the SDK truly cannot do something, build it — but leave a comment explaining why the SDK can't and link the upstream issue or doc gap. The agent brick's bespoke executor/registry/tool-wrapper layer is the cautionary tale this principle exists to prevent.

  *Exemplar of the "build it but document the gap" clause:* `components/agent/src/factory/agent/executors/_workflow_manager.py` subclasses `strands_tools.workflow.WorkflowManager` to inject plugins (bd `python-factory-pfg3`) and honor per-task `timeout` (bd `python-factory-2gao`). Both upstream bds are cited in the file's docstring, both override sites are guarded by a canary test (`test_canary_sdk_method_names_present`) that fails fast on a future SDK rename, and `strands-agents-tools` is exact-pinned so a minor bump is a deliberate review event rather than a silent break.

  *Exemplar — Strands `MCPClient` data-loss subclass:* `components/agent/src/factory/agent/runtime/adapters/strands_mcp_client_factory.py` (`FactoryMCPClient`) overrides the public `map_mcp_content_to_tool_result_content` extension point in exact-pinned Strands 1.50.2 to preserve `EmbeddedResource.uri` + `mimeType` through content-block flattening. Upstream issue [#2251](https://github.com/strands-agents/sdk-python/issues/2251) and PR [#2370](https://github.com/strands-agents/sdk-python/pull/2370) promoted the seam but did not fix the data drop. Local upstream behavior work is tracked under bd `python-factory-0g0gg`; the canary pins the public signature and `_handle_tool_result` dispatch. bd `python-factory-nmzlk`. The full sunset table lives in `.agents/steering/upstream-sdk-shims.md#active-upstream-prs-were-watching`.

  *Exemplar — agent-layer fix when neither Bedrock nor Strands exposes the knob:* `components/agent/src/factory/agent/plugins/parallel_tool_dedup.py` clamps duplicate parallel `tool_use` blocks via `BeforeToolCallEvent.cancel_tool`. Bedrock Converse has no `disable_parallel_tool_use` route — not on `additionalModelRequestFields` (rejected at runtime because it conflicts with `toolConfig.toolChoice`; Strands `models/bedrock.py:301,307`) and not via `anthropic-beta` headers — and the Strands `ToolChoice` union (`types/tools.py:104-170`) is closed with no parallel-control field. The plugin pattern is transport-agnostic across Bedrock / Anthropic / Nova / Llama / Ollama. bd:python-factory-ads4; strands-expert verdict `29dbd5b6` corrects prior `8da46474` (which had recommended the `additionalModelRequestFields` route), meta-architect APPROVE `8659e552`. Regression pinned by `test_build_chat_model_does_not_add_tool_choice_to_additional_fields` so a future agent can't reintroduce the dead end silently.

  **Read the dispatcher source for third-party FE SDKs.** When integrating a third-party FE SDK that ships its own dispatcher (CopilotKit, Vercel AI SDK, AG-UI client, etc.), the design phase MUST read the dispatcher source — not just the wire-format docs. Wire-format docs describe the contract; dispatcher source describes the actual runtime behavior. The two diverge often enough that "we read the docs and shipped" is not a defense.

  *Cautionary tale.* `python-factory-115z` (canvas-aware FE-tool round-trip) shipped a design that read the AG-UI wire format but never opened `@copilotkitnext/core/dist/index.mjs`. CopilotKit's `processAgentResult` skip predicate (`newMessages.findIndex(m => m.role === "tool" && m.toolCallId === id) === -1`) was the actual contract — backend `TOOL_CALL_RESULT` for FE tools makes the dispatcher think the tool was already executed server-side and skip the FE handler. The bug landed silently because no test rendered a real `<CopilotKitProvider>`. The smoke that found it was a human dragging the chat sidebar.

  *Operational rule.* Before approving an SDK integration design, the meta-architect or strands-expert must include a one-paragraph note that names the dispatcher file path, the version pinned, and the specific predicate or routing function the design depends on. If you can't cite the dispatcher source, you haven't done the homework.
- **Polymorphic/Agnostic**: All bricks use adapter pattern via `runtime/ports.py` Protocol interfaces. No hardcoded backends. Views are transport-agnostic data.
- **Clean Architecture**: Business logic in `runtime/`, MCP surface in `mcp/`, public API in `interface.py`.
- **Gateway Architecture**: Bases (API, Worker) are pure transport shells. They depend ONLY on the MCP aggregator, never on individual bricks.

## Code Quality Principles

- **<200 LOC**: Every file stays under 200 lines. Split into `mcp/`, `runtime/` subdirs if needed.
- **No Cross-Imports**: Components import only `factory.<other>.interface`, never internals.
- **No Bespoke Logic in Bases**: API, Worker are pure transport shells. They NEVER contain brick-specific formatting, routes, or logic.
- **Views as Data**: Views are declared as dicts in the brick's `mcp/views.py`. Components reference tools by name, not by URL. Adapters handle rendering.
- **DRY**: Don't repeat yourself. Extract shared patterns into utilities or shared modules.
- **SRP**: Each module, class, and function has a single, clear responsibility.

## Testing Principles

- **Test Behavior, Not Internals**: Tests verify what code does, not how it does it.
- **Edge Cases Matter**: Empty inputs, nulls, boundary values, unicode, large inputs.
- **Tests Must Be Independent**: No test depends on another test's state or execution order.
- **Property-Based Testing with Hypothesis**: Every brick with stateful operations (CRUD, state transitions, data transformations) MUST have Hypothesis property tests. Use `@given` for input fuzzing and `RuleBasedStateMachine` for stateful operation sequences. Define invariants that must hold across all inputs, not just hand-picked examples. See `components/agent/test/factory/agent/test_job_manager_stateful.py` as the canonical exemplar. Bricks that are pure pass-through or config-only (http, logger, mcp_utils) may skip this.

## Documentation Principles

- **Docs Follow Code**: When code changes, related docs (including steering files and agent rules) must be updated.
- **WHY Over WHAT**: Code shows what it does. Docs explain why.
- **Accuracy Over Completeness**: Wrong docs are worse than no docs.

## Workflow Principles (How the Team Works Together)

The factory has specialist sub-agents (`meta-architect`, `strands-expert`, `implementer`, `qa-tester`, `doc-writer`, `security-engineer`, `ux-designer`, `refactorer`, `context-gatherer`, `debugger`, `security-reviewer`). The orchestrating agent (the one you're talking to) is responsible for using them — not as advisory suggestions, but as the actual team that does the work. The agent brick's ~7,000 LOC of bespoke drift is the cautionary tale this section exists to prevent.

### The orchestrator's flow

When a request comes in:

1. **Declare the bd_id** — claim a bd issue if one exists, or state `"no-bd: <one-line reason>"` for ad-hoc work. All memory entries this turn will be tagged with this id.
2. **Gather context** if you don't already have it — launch `context-gatherer` for unfamiliar code, multi-brick changes, or any time you'd otherwise have to guess. Do NOT skim and assume.
3. **Clarify** if intent is ambiguous — ask the user before guessing. One round of clarifying questions is cheaper than the wrong implementation.
4. **Spec it** for non-trivial work — anything spanning 3+ files or introducing new concepts gets a brief markdown spec in `.kiro/specs/<bd-id>/` (design.md at minimum). Skip for typo fixes, single-line bug fixes, and well-scoped beads with clear descriptions.
5. **Design phase** — `meta-architect` + relevant SDK expert (e.g. `strands-expert` for Strands work) in parallel where independent. Output: design verdict logged to memory.
6. **Implementation phase** — `implementer` works against the approved design. Pass context files explicitly.
7. **Verify phase** — `qa-tester` adds property tests, runs spine canaries, confirms snapshot tests pin payloads.
8. **Document phase** — `doc-writer` updates steering, recipes, BRICK.yaml as needed.
9. **Security phase** — `security-engineer` reviews when scope warrants (auth, secrets, injection, infra).
10. **Coordinate** — orchestrator runs `foreman_guardian_check`, verifies all phase outputs, ships.

Phases that are independent run in parallel. Phases that gate each other (Design → Implement → Verify) run in order.

### Mandatory specialist consultation

The orchestrator MUST consult the listed specialist before code matching the trigger:

- **SDK integration code** (`runtime/adapters/strands_*`, `runtime/adapters/bedrock_*`, `runtime/adapters/strands_mcp_graph*`, `executors/swarm*`, `executors/graph*`) → `strands-expert` (or equivalent SDK expert).
- **New brick, base, or runtime adapter** → `meta-architect`.
- **New event type, payload schema, or subscription** → `meta-architect`.
- **>150 LOC delta in a single file** → `meta-architect` for design review.
- **Adding/modifying a Pydantic contract** (`learning_contracts.py`, any `*_contracts.py`) → `meta-architect`.
- **Agent prompts or skill files** (`registry/defaults_*.py`, `skills/*/SKILL.md`) → `strands-expert`.
- **Steering files or hooks that govern agent behavior** (`.agents/steering/*`, `.kiro/hooks/*`, `.kiro/agents/*`, `.kiro/skills/*`) → `meta-architect`.

**Trivial-change exemption** — typo fixes, comment-only edits, single-line bug fixes, version bumps, and dependency-only changes skip mandatory consultation. Use judgment honestly; if the trivial change exposes a real design question, consult.

**Grandfather clause** — pre-existing code that violates SDK-First or any other principle is tracked under `python-factory-sd72` (Strands modernization epic). New code MUST comply. Remediation of existing violations proceeds per that epic. The audit does not block work on legacy files.

### Logging team decisions to the control-plane runtime memory

Every specialist consultation gets one memory entry via the existing memory brick. Future sessions and audit hooks search by content prefix.

```
call_brick_tool(brick_name="memory", tool_name="memory_store", arguments={
  "content": "[CONSULT bd:<id> phase:<design|implement|verify|document|security> specialist:<name>] <verdict>: <one-paragraph summary>",
  
  "category": "fact",
  "metadata": {
    "bd_id": "<id>",
    "specialist": "<name>",
    "phase": "<phase>",
    "verdict": "APPROVE|APPROVE_WITH_NOTES|BLOCK",
    "files_reviewed": ["..."]
  }
})
```

The `[CONSULT bd:<id>]` content prefix is distinctive enough that semantic search reliably returns it. Use it consistently or the audit can't find the trail.

### No short-circuiting

The orchestrator MAY NOT skip a mandatory consultation by claiming "I have all the context." That rationalization is exactly what produced the agent-brick drift. If a trigger fires, the consult happens. If you genuinely had the context from earlier in the same session, log a memory entry referencing that prior consult — don't pretend it didn't need to happen.
