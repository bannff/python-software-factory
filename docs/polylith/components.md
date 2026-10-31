# Components

## Goal
Describe the shared logic bricks (`components/`) and how to work with them.

## Guidance
- Components should expose public surfaces via `interface.py` (and `server.py` when they are an MCP entrypoint).
- Avoid cross-component imports; depend on `factory.<component>.interface`.
- Cross-brick runtime choreography should prefer documented event contracts and projections over bespoke write models; see `learning-event-taxonomy.md`.

## Per-component discoverability
Prefer MCP-first discoverability when a component exposes an MCP server:
- Use stable MCP contract tools (e.g., `get_capabilities`, `describe_config_schema`).
- Add per-component pages only when they add durable context beyond what MCP can describe.

## Inventory

The factory has 29 components. See `BRICKS_INDEX.yaml` for the authoritative list with descriptions and features.

Key components by domain:

| Domain | Components |
|--------|------------|
| AI/Agent | `agent`, `llm_gateway`, `memory`, `evals` |
| Auth/Security | `auth`, `permissions`, `security` |
| Data | `kb`, `storage`, `cache`, `graph` |
| Infrastructure | `config`, `logger`, `telemetry`, `events`, `sandbox` |
| Integration | `http`, `integrations`, `notification`, `browser` |
| Business | `payments`, `workflow`, `blockchain` |
| UI | `ui`, `backend` |
| Tooling | `foreman`, `mcp_utils`, `test`, `machine_learning` |
