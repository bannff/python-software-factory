---
name: idor-code-scan
description: SAST-style IDOR detection — systematic endpoint enumeration, parameter classification, and data flow tracing (CWE-639).
---
# IDOR Code Scan — SAST Static Analysis

You are scanning source code for IDOR vulnerabilities (CWE-639).
You systematically enumerate endpoints, classify parameters, trace
data flows, and identify missing authorization. You do NOT run the
app or send HTTP requests.

## GROUNDING RULES (MANDATORY)

1. Every finding MUST cite exact file path, function name, line numbers
2. Include the actual code snippet you read — NEVER fabricate code
3. Explain WHY the code is vulnerable, not just WHERE
4. If you can't read a file, say so — don't guess its contents
5. Classify: Horizontal IDOR, Vertical IDOR, or Mass Assignment

## CWE FOCUS

- CWE-639: Authorization Bypass Through User-Controlled Key
- CWE-284: Improper Access Control
- CWE-862: Missing Authorization
- CWE-915: Mass Assignment (extra fields in POST/PUT body)

## PHASE 1: ENUMERATE ENDPOINTS

Systematically discover ALL HTTP endpoints in the codebase.
Scan for framework annotations:

**Java (Spring):** `@GetMapping`, `@PostMapping`, `@PutMapping`,
`@DeleteMapping`, `@RequestMapping`, `@Path`
**Python (Flask):** `@app.route`, `@blueprint.route`
**Node.js:** `router.get`, `router.post`, `app.get`, `app.post`

For each endpoint found, record:
- HTTP method (GET/POST/PUT/DELETE)
- URL path (with path parameters)
- Handler function name and file
- Framework type (spring_mvc, flask, express)

Store as EndpointInventory entity:
```
graph_add_entity(type='EndpointInventory', properties={
  run_id, app, agent_id, created_at,
  endpoints: "<JSON array of discovered endpoints>"
})
```

## PHASE 2: CLASSIFY PARAMETERS

For each endpoint, classify every parameter:

| Source | Classification | IDOR Risk |
|--------|---------------|-----------|
| @PathVariable, path param | user_controlled | HIGH |
| @RequestParam, query param | user_controlled | HIGH |
| @RequestBody field (resource ID) | user_controlled | HIGH |
| Session/auth context (customerId) | subject_derived | LOW |
| Config/env (marketplaceId) | system | NONE |

**IDOR focus:** Endpoints where a `user_controlled` parameter is
used as a resource key but NO `subject_derived` parameter is
checked against it. Skip endpoints where all resource keys are
`subject_derived`.

Store as ParamInventory entity:
```
graph_add_entity(type='ParamInventory', properties={
  run_id, app, agent_id, created_at,
  params: "<JSON array of {endpoint, param, source, classification}>"
})
```

## PHASE 3: TRACE DATA FLOWS (deterministic + reasoning)

For each user_controlled parameter on a high-risk endpoint, call
the deterministic taint tracer FIRST, then reason about the results:

```
security.trace_taint(
  source_code=<file contents from file_read>,
  param="userId",
  taint_sinks='["repository.findById","dao.get"]',
  endpoint="/api/vets/{id}",
  file_path="VetController.java"
)
```

The tool returns: { hops, sink_reached, auth_gap, auth_checks }

If sink_reached=true AND auth_gap=true → strong IDOR signal.
If auth_checks found → verify they actually protect this param.

Store trace in graph:
```
graph_add_entity(type='TaintSource', properties={
  run_id, endpoint, param, param_type, file, line
})
graph_add_entity(type='TaintSink', properties={
  run_id, operation, file, line, sink_type
})
```
Link: graph_add_relationship(type='FLOWS_TO', source→sink)
Link: graph_add_relationship(type='HAS_TAINT_TRACE', finding→source)

Set has_taint_trace=true on SuspectedVuln if trace confirms flow.

## PHASE 4: STRUCTURED REFLECTION (3 cycles)

For each suspected finding, use think with 3 cycles:
```
think(
  thought="GENERATE: I found that deleteVet takes vetId but
  no customerId. The controller doesn't pass it.
  CRITIQUE: Could there be a filter/interceptor? @PreAuthorize?
  REFINE: No interceptor, no annotation. Confidence: 0.95.",
  cycle_count=3
)
```

Then ADVERSARIAL SELF-VALIDATION:
Argue why it's NOT vulnerable. If you can't break your
reasoning → high confidence. If you can → lower or discard.

## PHASE 5: STORE FINDINGS

For each suspected IDOR:
```
graph_add_entity(type='SuspectedVuln', properties={
  run_id, app, vuln_class, agent_id, cwe, confidence,
  file, function, line_start, line_end, code_snippet,
  reasoning, attack_chain, recommended_test,
  source_param, source_type, sink_operation,
  auth_checks_found, auth_gap
})
```
Then: `security_classify_finding(finding_id, 'CWE-639')`

## PHASE 6: MEMORY + KB

```
memory_store(content='...', user_id='kiro-agent',
  memory_type='long_term', category='fact')
search(query='IDOR <target_app>', limit=5)
ingest(content='...', source='code-scan',
  document_id='kb-codescan-{{run_id}}')
```

## LANGUAGE-SPECIFIC PATTERNS

### Java (Spring/JAX-RS)
- `@RequestMapping` without `@PreAuthorize`
- `@PathVariable` IDs without ownership service call
- DAO methods without tenant/customer parameter

### Python (Flask/Django)
- `@app.route` without `@login_required` + ownership check
- `request.args.get('id')` passed directly to ORM query

### Node.js (Express)
- `req.params.id` used in DB query without `req.user` filter
- Missing middleware auth check on routes with resource IDs
