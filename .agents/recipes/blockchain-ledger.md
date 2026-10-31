# Recipe: Blockchain Agent Economy

Use the Blockchain brick’s strict 24-tool MCP boundary to inspect or operate a hash-chained agent economy.

## Bricks Used
- `blockchain` — Wallets, transfers, bounties, hash-chain verification, and the ledger view.

## Prerequisites
- The Blockchain brick is available through the control-plane runtime progressive discovery.
- The default `mock_ledger` adapter requires no AWS services.
- Set `BLOCKCHAIN_ENABLE_AUTHORING_TOOLS=1` only when deliberately seeding a local development economy.

## Boundary Contract

All 24 tools accept strict same-brick Pydantic v2 inputs and return `ToolResult[OutputDTO]`. Keep the flat tool arguments shown in the tool schema. A normal ledger-negative outcome is successful typed data, not a transport failure: lookup outputs set `found=false` with an error, and rejected mutations set their domain `success`/`ok` field to `false` with an error. Inspect the returned DTO before using its payload.

The two authoring tools are always discoverable, but `blockchain_authoring_seed_economy` returns `data.ok=false` and `error="authoring_disabled"` unless `BLOCKCHAIN_ENABLE_AUTHORING_TOOLS=1`.

## Steps

### Step 1: Discover the strict surface

```python
kiroPowers(
    action="use", powerName="the control-plane runtime", serverName="the control-plane runtime",
    toolName="get_brick_tools", arguments={"brick_name": "blockchain"},
)
# Expect 24 tools: 13 deterministic, 9 operational, and 2 authoring.
```

### Step 2: Invoke a ledger tool through the gateway

```python
kiroPowers(
    action="use", powerName="the control-plane runtime", serverName="the control-plane runtime",
    toolName="call_brick_tool",
    arguments={
        "brick_name": "blockchain",
        "tool_name": "blockchain_my_wallet",
        "arguments": "{}",
    },
)
```

For every remaining tool, retain this canonical gateway call shape and replace only `tool_name` plus the JSON-stringified `arguments` value. For example, create `alice` with `blockchain_create_wallet` and `{"owner_id":"alice","initial_balance":1000}`; transfer funds with `blockchain_transfer`; then post and claim an escrowed bounty with `blockchain_post_bounty` and `blockchain_claim_bounty`. An insufficient balance or unknown wallet remains typed domain-negative data.

### Step 3: Verify ledger state and the declared view

Use `blockchain_verify_chain`, `blockchain_get_dashboard_summary`, and `blockchain_get_views` with empty JSON arguments. `blockchain_get_views` returns the declared `Economy & Ledger` view, which renders transaction, activity, related-graph-entity, and bounty inspectors from the dashboard summary. Its drill-downs call the typed block, wallet, activity, and graph-context tools.

### Step 4: Seed a local economy only when authorized

Call `blockchain_authoring_get_status` first. Invoke `blockchain_authoring_seed_economy` with `{"agent_count":5,"initial_balance":1000}` only after the gate reports enabled.

## Success Criteria
- [ ] Discovery reports 24 tools: 13 deterministic, 9 operational, and 2 authoring.
- [ ] Consumers read successful payloads from the `ToolResult` DTO and handle typed negative outcomes.
- [ ] `blockchain_verify_chain` reports a valid chain after the ledger operations.
- [ ] `blockchain_get_views` returns the `blockchain-economy` declaration.
- [ ] Economy seeding is attempted only after the authoring gate reports enabled.

## API Reference

| Brick | MCP boundary | Contract |
|-------|--------------|----------|
| `blockchain` | 24 flat FastMCP tools | Strict Pydantic v2 ingress; `ToolResult[OutputDTO]` egress |
| `blockchain` | `blockchain_get_views` | Typed view declaration for the Economy & Ledger inspector |
| `blockchain` | `blockchain_authoring_*` | Always registered; mutation behavior is gated by `BLOCKCHAIN_ENABLE_AUTHORING_TOOLS` |

## MCP Tools

| Tool | Category | Description |
|------|----------|-------------|
| `blockchain_get_capabilities` | deterministic | Capabilities and available backend |
| `blockchain_health_check` | deterministic | Ledger readiness |
| `blockchain_describe_config_schema` | deterministic | Supported configuration |
| `blockchain_get_chain_info` | deterministic | Chain summary |
| `blockchain_get_balance` | deterministic | Wallet balance or typed missing-wallet outcome |
| `blockchain_get_wallet` | deterministic | Wallet details or `found=false` |
| `blockchain_list_transactions` | deterministic | Optional wallet-filtered transaction history |
| `blockchain_get_block` | deterministic | Block by height or `found=false` |
| `blockchain_verify_chain` | deterministic | Hash-chain integrity check |
| `blockchain_get_dashboard_summary` | deterministic | View data for ledger activity, bounties, and graph context |
| `blockchain_get_activity` | deterministic | Filtered ledger activity |
| `blockchain_get_entity_graph_context` | deterministic | Related graph entities |
| `blockchain_get_views` | deterministic | Economy & Ledger view declaration |
| `blockchain_my_wallet` | operational | Get or create the caller wallet |
| `blockchain_create_wallet` | operational | Create a wallet |
| `blockchain_transfer` | operational | Transfer tokens |
| `blockchain_mint` | operational | Mint tokens from treasury |
| `blockchain_post_bounty` | operational | Post an escrowed bounty |
| `blockchain_claim_bounty` | operational | Claim a bounty and release escrow |
| `blockchain_cancel_bounty` | operational | Cancel an open bounty and return escrow |
| `blockchain_list_bounties` | operational | Optional status-filtered bounties |
| `blockchain_reconcile` | operational | Recompute wallet balance from history |
| `blockchain_authoring_get_status` | authoring | Report whether authoring is enabled |
| `blockchain_authoring_seed_economy` | authoring | Seed local wallets when authoring is enabled |
