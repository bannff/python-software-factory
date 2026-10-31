# py7t9 — Tokenless third-party credential egress foundation

Bead: `python-factory-py7t9` (epic `python-factory-nmj61`).
Architecture consult `3b3c95ae`; security consult `13a3b999`. Raw-token-over-MCP is **BLOCKED**.

## Invariant

Raw client secrets, refresh tokens, and access tokens NEVER cross the **public** MCP
boundary (agents, Workflow, events, telemetry, logs, evidence, discovery, resources,
public tool results). The public boundary carries only: opaque `connection_ref`,
provider/route IDs, typed request payloads, request digests, and sanitized business
results. Durable secrets live only as ciphertext at rest; access tokens live only
inside Auth's broker call stack (in-memory cache, never persisted, never returned).

The internal `auth → storage` slot handoff is service-only (in-process, caller-bound
claims) and follows the existing `auth.issue_workload_credential` precedent, which
already returns a raw token through a service-only path. Service-only in-process
payloads are NOT the public MCP boundary.

## Ownership split

| Layer | Owns | Must NOT |
|-------|------|----------|
| **Storage** | encrypted mutable credential bytes; owner/tenant/provider/connection/slot-kind-scoped slots; generation + version; fenced CAS; tombstone; rekey; ciphertext durability | OAuth/provider semantics |
| **Auth** | provider/route registry; delegated + client-credentials flows (FAKE here); refresh/revoke; scope policy; access-token cache + refresh single-flight; fixed-route credential-injecting egress | let a token leave its call stack |
| **Integrations/Documents** | semantic provider actions; idempotency; safe result projection; opaque connection/action refs only | receive provider tokens |
| **mcp_utils / mcp_server** | neutral service handoff: `CredentialSlotBinding`, `CredentialEgressBinding`, one-shot caller-bound claims, `NativeEnvelopeInvoker` support | any provider/business logic in the base |

## Layer A — mcp_utils bindings (foundation)

`service_bindings.py`
- Extend `BindingKind` with `"credential_slot"`, `"credential_egress"`.
- `CredentialSlotBinding(tenant_id, owner_id, provider_id, connection_ref, slot_kind, generation:int)` — binds one exact storage slot op. `slot_kind ∈ {client_secret, refresh_token}`.
- `CredentialEgressBinding(provider_id, route_id, connection_ref, request_digest)` — binds one exact auth egress op (`request_digest` = sha256 of the canonical request).
- Add to `InvocationBinding` union, `binding_kind()`, `binding_matches()`, `__all__`.

`service_only.py` — add both kinds to the `service_only()` and `service_binding()` validation sets.

`interface.py` — re-export both new binding dataclasses.

## Layer D — base `NativeEnvelopeInvoker`

- `__call__` gains `credential_slot=None`, `credential_egress=None` kwargs.
- `_claims_for` includes them in the exactly-one-binding-supplied count and adds two branches parsing the new bindings. Unlike attempt/execution these are NOT coupled to `run_id` (tenant/owner scoped). No provider/business logic added — base only parses the binding and mints claims.

## Layer B — Storage credential slots (encrypts; owns keys)

New port `runtime/ports/credential_slots.py`: `CredentialSlotStore` Protocol —
`write(id, secret, *, expected_generation, expected_version)`, `read(id, *, expected_generation)`,
`revoke(id, *, expected_generation)`, `rekey(id)`. Receipts carry `(generation, version)` — never a secret.

New adapter `runtime/adapters/credential_slots_sqlite.py`: reuses the AES-256-GCM DEK-wrap
envelope + `ProtectedContentKeyProvider` (import from `mcp_utils.interface`). Distinct from the
immutable `ProtectedArtifact` store — these are **mutable** with generation/version.
- Schema `credential_slots(tenant_id, owner_id, provider_id, connection_ref, slot_kind,
  generation, version, envelope, tombstoned, created_at, updated_at,
  PRIMARY KEY(tenant_id,owner_id,provider_id,connection_ref,slot_kind))`. WAL.
- **AAD** binds tenant/owner/provider/connection/slot_kind/generation/version/key_id — so a
  record cannot be replayed under a different identity or generation.
- **Fenced CAS**: `version` is the optimistic-concurrency token (bumped every successful write);
  `generation` is the fence (bumped on revoke, invalidating all prior authority). A writer with
  stale `(generation, version)` fails via `BEGIN IMMEDIATE` + `UPDATE ... WHERE generation=? AND
  version=? AND envelope=?` + `rowcount != 1`.
- Foreign / missing / tampered / tombstoned → one indistinguishable opaque error.

Service-only MCP tools (`mcp/credential_slots.py`, `@service_only(callers={"auth"},
binding="credential_slot")`, registered directly in `server.py`, excluded from `mcp/__init__`):
`storage.credential_slot_write`, `_read`, `_revoke`, `_rekey`. Typed DTOs under
`mcp/contracts/credential_slots.py`. `_read` returns the decrypted secret only to `auth`.

## Layer C — Auth broker (owns lifecycle; token never leaves)

- `runtime/egress_registry.py` — immutable `ProviderRoute(provider_id, route_id, origin[https],
  method, path_template, required_scopes, request_schema, result_schema, max_bytes, timeout_s,
  redirect_policy="none")`. Registry maps `(provider_id, route_id)`. Callers supply NONE of URL /
  method / headers / scopes / token endpoint — only provider+route IDs + a typed request payload.
- `runtime/egress_models.py` — strict `EgressRequest` / `EgressResult` DTOs; `request_digest`.
- `runtime/credential_broker.py` — in-memory access-token cache keyed by
  `(tenant, owner, provider, connection)`; `threading.Lock` single-flight so concurrent refresh
  ⇒ exactly one provider call + one CAS winner; at most one forced refresh/retry after a provider
  401; revoke bumps slot generation and invalidates the cache before remote cleanup. Reads durable
  secret via `SecretStorePort`. Errors expose stable safe codes only.
- `runtime/ports.py` additions — `SecretStorePort`, `CredentialedEgressPort`, `TokenAcquirer`.
- `runtime/adapters/secret_store_service.py` — `SecretStorePort` impl that calls the storage slot
  tools through `get_service("tool_invoker_for_caller")("auth")` with a `credential_slot` binding.
- `runtime/adapters/fake_providers.py` — `FakeMicrosoftDelegated` + `FakeAdobeClientCredentials`
  token acquirers (NO network). Real Graph/Adobe belong to child stories.
- `mcp/egress.py` — hidden `auth.credentialed_egress` (`@service_only(callers={"integrations"},
  binding="credential_egress")` + `@operational`), registered in `server.py`, excluded from
  `mcp/__init__`. Validates request against the route, delegates to the broker, returns a sanitized
  result. Only caller `integrations` is authorized now (no `documents` until that brick exists).

## Acceptance path

`MCPAggregator → NativeEnvelopeInvoker.for_caller("integrations") → auth.credentialed_egress
→ broker → SecretStorePort → storage.credential_slot_read (caller=auth)` for BOTH the
Microsoft-delegated fake and the Adobe client-credentials fake through the identical path.

## Test plan (Hypothesis stateful + property)

- Slot state machine: generation/version CAS, isolation (tenant/owner/provider/connection),
  tombstone, rekey (rewrap preserves plaintext, bumps nothing observable to callers).
- Negative: wrong caller / tenant / owner / provider / route / generation / scope; replay;
  mixed/partial bindings — all fail **before** decrypt/network.
- Concurrency: parallel refresh ⇒ exactly one provider refresh + one CAS winner.
- Revocation/tombstone invalidates cache.
- Injection: caller-supplied URL/method/Authorization/cookie/arbitrary headers/scope rejected.
- No token-bearing fields in any public MCP schema/discovery.
- Canary client-secret / refresh-token / access-token absent from every public MCP
  argument/result/content, discovery, error, log, event, Workflow/session/telemetry capture,
  and plaintext SQLite / WAL / SHM.

All changed Python files < 200 LOC. `foreman_guardian_check` + affected suites green.
