"""Curated tool selection for the Companion X chat agent.

Defines WHICH MCP tools the chat agent gets access to.
The HOW (in-process callables vs MCPClient HTTP) is the adapter's job.

Tool prefixes map to bricks. We select a useful subset — not all 300+.
Selection is intentionally **stable** — does not depend on user query.
The chat agent is cached per ``thread_id`` to keep conversation history;
rebuilding it with a different tool set on every turn would either lose
memory (cache miss) or leave it with stale tools (cache hit).
"""

from __future__ import annotations

# Brick prefixes the chat agent should have access to.
# Each prefix matches tools like "{prefix}_{tool_name}".
ALLOWED_BRICK_PREFIXES = [
    "security",       # security scanning, posture checks
    "graph",          # neo4j graph queries, topology
    "kb",             # knowledge base search, ingest
    "evals",          # evaluation suites, benchmarks
    "cache",          # key-value cache ops
    "storage",        # blob/object storage
    "events",         # event stream queries
    "notification",   # send alerts
    "telemetry",      # health, metrics, spans
    "ml",             # ML experiments, models
    "auth",           # auth status checks
    "permissions",    # permission lookups
    "agent",          # swarm registry, launch, workflow status
    "metrics",        # portfolio metrics, regression gate
    "sandbox",        # Docker sandbox provisioning + execution
    "blockchain",     # agent economy, wallets, bounties
    "games",          # game sessions, CTF, RL environment
    "memory",         # companion memory (store/retrieve)
]

# Specific tools to always include (even if prefix doesn't match).
# Single-prefix names — the chat agent reads from the FLAT view, which
# mounts each brick's FastMCP without a namespace, so brick-decorated
# names like ``ui_get_views`` keep their single ``ui_`` prefix on the
# chat surface (bd:python-factory-3hkqx).
EXTRA_TOOLS: list[str] = [
    "ui_get_views",
    "ui_render_brick_view",
    "ui_paint_canvas",
]

# Tools to explicitly exclude (noisy, dangerous, or internal-only)
EXCLUDED_TOOLS: set[str] = {
    "agent_reason",          # prevent recursion
    "agent_get_views",       # UI-only, not useful in chat
    "agent_health_check",    # internal contract tool
    "agent_get_capabilities", # internal contract tool
    # ad-hoc inline launcher — dashboard-only; chat uses auditable
    # registry spawns (spawn_swarm). BOTH prefix forms are excluded: the
    # chat agent reaches the FLAT view (single `agent_` prefix), the
    # aggregator/dashboard path uses the double `agent_agent_` form.
    # Listing only the double form let `agent_launch_swarm` leak onto the
    # chat surface (bd:python-factory-esb6n; strands-expert verdict e681a849).
    "agent_launch_swarm",
    "agent_agent_launch_swarm",
    # NOTE: ``agent_agent_create_agent`` is NO LONGER excluded
    # (bd:python-factory-czpw.1). The user EXPLICITLY WAIVED the
    # chat-exclusion guardrail (on record, meta-architect verdict
    # ``dbae0646``), reversing the prior security gate (9d6a73fb /
    # 6dde9717). The chat agent now CREATES personas on the fly and then
    # SPAWNS them via ``spawn_subagent``. The ``@authoring`` decorator
    # STAYS on ``agent_create_agent`` — ``SUPER_AGENT_ENABLE_AUTHORING_TOOLS``
    # remains the operator kill-switch. ``agent_launch_swarm`` stays
    # excluded (the raw 600-tool inline launcher is still dashboard-only).
}


def select_tools(all_tool_names: list[str]) -> list[str]:
    """Filter the full tool list to the chat agent's curated subset.

    Stable, prefix-based filtering — does not depend on user query.

    Args:
        all_tool_names: All available MCP tool names from the aggregator.

    Returns:
        Sorted list of tool names the chat agent should use.
    """
    selected: set[str] = set()

    for name in all_tool_names:
        if name in EXCLUDED_TOOLS:
            continue
        for prefix in ALLOWED_BRICK_PREFIXES:
            # Match both underscore-style (graph_query) and dot-style (sandbox.provision)
            if name.startswith(f"{prefix}_") or name.startswith(f"{prefix}."):
                selected.add(name)
                break

    selected.update(t for t in EXTRA_TOOLS if t in all_tool_names)
    selected -= EXCLUDED_TOOLS

    return sorted(selected)
