# Bases

## Goal
Describe entry points and orchestration (`bases/`).

## Guidance
- Bases wire components together and define runnable entrypoints.
- If a base exposes an MCP server, it should follow the same stable discovery contract as components.

## Inventory

| Base | Description |
|------|-------------|
| `api` | HTTP API entry point with REST and GraphQL adapters |
| `blueprint` | System configuration & service discovery (The Construct) |
| `dashboard` | FastHTML + HTMX + PicoCSS UI |
| `mcp_server` | Unified MCP aggregator combining all brick servers |
