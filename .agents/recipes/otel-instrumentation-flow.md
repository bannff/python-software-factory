# Recipe: OTEL → Telemetry → MCP Materialization

OTEL/OTLP is the observation wire; MCP is the platform highway. Telemetry owns the authenticated OTLP HTTP/gRPC receiver, raw evidence, and bounded materialization. A Collector is optional transport/processing only.

## Enforceable boundary

The receiver converts OTLP to bounded Pydantic-v2 `TelemetryIngestBatch`; authenticated request context—not caller DTO fields—binds producer, principal, tenant, visibility, and source namespace. Durable idempotency keys are `(tenant, verified_producer, batch_id)` and `(tenant, verified_producer, source_id)`, with canonical fingerprints: equal replay is duplicate; changed replay conflicts; each item has outcome and retry eligibility.

`TelemetryReferenceRead` authorizes the same bound context before returning permitted fields. `TelemetryMaterialize` accepts retained telemetry references and activated immutable mapping `(mapping_id, version)` references. Every downstream MCP call inherits the bound context.

Mappings pin target brick/capability/version, accepted signals, maximum fan-out, and output provenance. Registry validation rejects Telemetry/Agent/Workflow targets, return-to-Telemetry paths, and every direct/transitive cycle. Callers cannot name arbitrary tools.

## Propagation and provider ownership

`run_id` is durable execution join; W3C trace/span IDs, session, agent, workflow, graph, and swarm IDs retain their own meanings. HTTP, event/queue, and negotiated MCP carriers preserve `traceparent`/`tracestate`; scalar context stays in the envelope. Invalid/untrusted carrier is rejected or policy-new-rooted.

Initialize one provider before Agent/Graph/Swarm creation; inject it into `StrandsTelemetry`; do not create a competing provider/export pipeline. Redaction/sampling precedes raw retention and records policy/version/outcome.

## Graph projection

Telemetry materializes only selected source references/summaries. Graph relationships deterministically derive from source/digest + relation + endpoints and atomically create-or-match or conflict. Rebuilds enumerate frozen durable source snapshots, checkpoint ordered cursors, process tombstones, and report reconciliation counts. Raw trace payloads remain in Telemetry.

## Proof

1. Verify Agent bootstrap precedes Strands creation and child W3C parentage is preserved.
2. Ingest and replay a bounded batch; prove retained evidence, duplicate/conflict behavior, scoped reads, and partial retry result.
3. Activate a valid mapping; prove a cyclic/forbidden mapping is rejected.
4. Materialize one Graph/Metrics reference; prove atomic relationship, tombstone/rebuild convergence, and subject-focused measurement.
5. Repeat across chat, native Graph/Swarm, remote MCP, and two unrelated domains.

`TELEMETRY_GRAPH_SINK` remains legacy compatibility evidence only; new work follows this contract.
