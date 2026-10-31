---
name: sandbox-ops
description: Deploy, operate, and PENTEST AWS resources in the LocalStack sandbox.
---
# Sandbox Operations & Pentesting

You are operating a LocalStack sandbox for security testing.

## Sandbox Tools

- `sandbox_list_environments()` — find sandbox env_id
- `sandbox_deploy_cfn(env_id, stack_name, template_body)` — deploy CFN
- `sandbox_describe_stack(env_id, stack_name)` — check stack
- `sandbox_execute(env_id, command)` — run AWS CLI commands

## Pentest Tools (security brick)

USE THESE for real exploitation, not just config checks:

- `security_pentest_scan(scan_type='web_fuzz', target='https://...')` — fuzz API endpoints
- `security_pentest_scan(scan_type='sql_inject', target='https://...')` — SQL injection
- `security_pentest_scan(scan_type='http_probe', target='https://...')` — probe HTTP
- `security_pentest_scan(scan_type='nuclei_scan', target='https://...')` — nuclei templates
- `security_pentest_scan(scan_type='port_scan', target='...')` — port scan
- `security_pentest_status(job_id)` — check scan status
- `security_pentest_results(job_id)` — get scan results
- `security.code_review(code, language, focus)` — review code for vulns
- `security.threat_model(target, context)` — STRIDE analysis

## Real Exploitation (not config checks)

Your goal is to PROVE vulnerabilities, not just find misconfigs.

### IDOR Test Pattern
```
# As user A, create a resource
sandbox_execute(env_id, 'aws dynamodb put-item --table-name X --item {"userId":{"S":"userA"},"data":{"S":"secret"}}')
# As user B, try to access user A's resource
sandbox_execute(env_id, 'aws dynamodb get-item --table-name X --key {"userId":{"S":"userA"}}')
# If it works → PROVEN IDOR
```

### Privesc Test Pattern
```
# List what the role can do
sandbox_execute(env_id, 'iam list-attached-role-policies --role-name X')
# Assume the role
sandbox_execute(env_id, 'sts assume-role --role-arn arn:aws:iam::000000000000:role/X --role-session-name test')
# Try to create a new admin user (proves privesc)
sandbox_execute(env_id, 'iam create-user --user-name backdoor')
sandbox_execute(env_id, 'iam attach-user-policy --user-name backdoor --policy-arn arn:aws:iam::aws:policy/AdministratorAccess')
```

### Data Exfil Test Pattern
```
# Read unencrypted data
sandbox_execute(env_id, 'dynamodb scan --table-name X --max-items 5')
# Download S3 objects
sandbox_execute(env_id, 's3 cp s3://bucket/file /tmp/exfil')
```

### API Abuse Test Pattern
```
# Hit unauthenticated endpoint
security_pentest_scan(scan_type='http_probe', target='https://api-endpoint/prod/path')
# Fuzz for injection
security_pentest_scan(scan_type='web_fuzz', target='https://api-endpoint/prod/path')
```

## AWS CLI Prefix
```
AWS_DEFAULT_REGION=us-east-1 AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test aws --endpoint-url=http://localhost:4566
```

## Workspace JSON Contract (recon → sandbox handoff)

The recon agent writes discovered resources to a workspace file, NOT the
graph. Read it before creating anything in LocalStack.

Workspace path: `/tmp/factory-sandbox/{env_id}/artifacts/`

### STEP 1 — Read the workspace `recon.json`
```
sandbox.execute(env_id, 'cat /tmp/factory-sandbox/{env_id}/artifacts/recon.json')
```
Parse it. The `resources` array has `{type, name, account}` entries — one
per resource to create. `security_profile` and `accounts` provide context.

### STEP 2 — Create each resource directly via `sandbox.execute`
No CloudFormation. AWS CLI per resource type (DynamoDB, Lambda, SQS, S3,
IamRole, etc.) against the LocalStack endpoint.

### STEP 3 — Write `sandbox-status.json` (NOT graph)
After each resource pass, collect statuses into the workspace file:
```
{"run_id": "<run_id>", "app": "<target_app>",
 "resources": [{"name": "...", "type": "...", "status": "created"}, ...]}
```
```
sandbox.execute(env_id,
  'cat > /tmp/factory-sandbox/{env_id}/artifacts/sandbox-status.json << EOF\n<json>\nEOF')
```
Do NOT write `SandboxResource` entities to the graph.

### STEP 4 — Mocks + validation update the same workspace file
After `sandbox.apply_service_mocks(...)`, read `sandbox-status.json`, add a
`mocks_applied` key, rewrite. After validation, add `validation_result`
the same way. Only the final `SandboxValidation` finding is graph-bound.
