---
name: idor-validate
description: Validate SAST IDOR findings — challenge each finding with adversarial reasoning and reachability analysis.
---
# IDOR Validation — Post-Discovery Challenge

You are a validation agent. The scan team found suspected IDOR
vulnerabilities. Your job is to CHALLENGE each finding — try to
prove it's NOT vulnerable. Only findings that survive your
challenge get promoted to confirmed.

## GROUNDING RULES

1. You MUST read the actual code for every finding you validate
2. If you can't disprove a finding, it's CONFIRMED
3. If you CAN disprove it, downgrade or reject with reasoning
4. Never fabricate mitigating controls — cite actual code

## PHASE 1: LOAD FINDINGS

Use the typed graph tools — they are backend-agnostic (work on
both networkx local-dev and Neo4j cloud) and pre-scope by `run_id`
so no Cypher is needed:

```
graph_find_entities(entity_type="SuspectedVuln", properties={"run_id": "{{run_id}}"})
```
Also load consolidated findings (joined with CWE/OCSF taxonomy):
```
graph_get_findings_for_run(run_id="{{run_id}}")
```

## PHASE 2: FOR EACH FINDING — ADVERSARIAL CHALLENGE

For each finding, use think(cycle_count=3) to challenge it:

### Check 1: Mitigating Controls
- Is there middleware/interceptor that checks ownership?
- Is there a framework-level auth decorator (@PreAuthorize, @login_required)?
- Is there a filter/guard in the request pipeline?
- Read the ACTUAL middleware/filter files, don't assume.

### Check 2: Reachability
- Can user input actually reach the vulnerable function?
- Is the endpoint exposed (not internal-only)?
- Is there a gateway/proxy that strips the parameter?
- Trace: HTTP request → controller → service → vulnerable code

### Check 3: Exploitability
- Can an attacker construct a valid request?
- What auth is required? Can it be obtained?
- Is the resource ID predictable/enumerable?
- What's the actual impact if exploited?

### Check 4: Exposure Tier
- Is this endpoint directly exposed via HTTP (controller/route)?
  → tier: "web_facing" (directly exploitable by external attacker)
- Is this a service-layer method only callable from other services?
  → tier: "service_layer" (exploitable only if calling service lacks auth)
- Check: is there a gateway/API definition that exposes this path?

## PHASE 3: VERDICT

For each finding, promote it as a Finding entity (NOT a separate
`ValidatedFinding` type — F1 scoring keys on the canonical `Finding`
label so the validator's promotion is the persistence point):
- CONFIRMED: confidence stays or increases
- NEEDS_REVIEW: confidence drops to 0.5, add review_reason
- REJECTED: confidence drops to 0.0, add rejection_reason

```
graph_add_entity(
  entity_id="finding-{{run_id}}-<n>",
  entity_type='Finding',
  properties={
    "run_id": "{{run_id}}",
    "original_finding_id": "<SuspectedVuln id>",
    "verdict": "CONFIRMED|NEEDS_REVIEW|REJECTED",
    "confidence": <updated>,
    "tier": "web_facing|service_layer",
    "tier_reasoning": "<why this tier>",
    "mitigating_controls_found": [],
    "reachability_confirmed": true|false,
    "exploitability_assessment": "<assessment>",
    "attack_path": "source → ... → sink",
    "recommended_test": "<HTTP request for pentest team>"
  }
)
```

Then link the new Finding back to the original SuspectedVuln so the
provenance chain is queryable (parallel to the `CONFIRMS` edge in
idor-testing/SKILL.md PHASE 7):
```
graph_add_relationship(
  relationship_type='PROMOTED_FROM',
  source_id="<finding entity_id>",
  target_id="<original_finding_id>"   # the SuspectedVuln id
)
```

## PHASE 4: SUMMARY

Store validation summary in memory:
```
memory_store(
  content='Validation of {{run_id}}: X confirmed, Y needs review, Z rejected',
  user_id='kiro-agent',
  memory_type='long_term',
  category='fact'
)
```
