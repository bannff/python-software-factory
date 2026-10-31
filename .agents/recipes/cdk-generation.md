# Recipe: CDK Generation

Validates the blueprint base's CDK generation pipeline: spec normalization, resolution, CDK rendering, and CI/CD pipeline generation.

## Why This Exists

AWS adapters declare infrastructure needs via `infrastructure_spec()` dicts. The blueprint base converts these into a deployable CDK L2 Python project — closing the loop from adapter declarations to IaC without manual authoring.

## Bricks Used

- **blueprint** — CDK generation, pipeline generation, spec validation

## Prerequisites

- No AWS credentials needed (generates files only, doesn't deploy)
- No Docker needed

## Scenario

Generate a CDK project for a system using storage (DynamoDB), events (SQS), and auth (Cognito). Then generate a CI/CD pipeline.

## Steps

### 1. Check supported services

```python
result = blueprint_list_supported_services()
# Returns: {"services": {"dynamodb": {...}, "sqs": {...}, "cognito-idp": {...}, ...}}
# Verify: 15 services listed, each with module/construct/alias
```

### 2. Validate specs before generation

```python
specs = [
    {"brick": "storage", "spec": {
        "service": "dynamodb", "construct": "Table",
        "props": {"billing_mode": "PAY_PER_REQUEST"},
    }},
    {"brick": "events", "spec": {
        "service": "sqs", "construct": "Queue",
        "props": {"visibility_timeout": 300},
    }},
    {"brick": "auth", "spec": {
        "provider": "aws", "service": "cognito-idp",
        "resources": [{"type": "AWS::Cognito::UserPool", "properties": {
            "auto_verified_attributes": ["email"],
        }}],
    }},
]

result = blueprint_validate_specs(specs=specs)
# Returns: {"valid": true, "resource_count": 3, "services_used": ["cognito-idp", "dynamodb", "sqs"],
#           "vpc_required": false, "errors": []}
```

### 3. Generate CDK project

```python
result = blueprint_generate_cdk(specs=specs, project_name="my-service")
# Returns: {"project": "my-service", "files": {
#   "cdk/app.py": "...",
#   "cdk/cdk.json": "...",
#   "cdk/requirements.txt": "...",
#   "cdk/stacks/auth_stack.py": "...",
#   "cdk/stacks/events_stack.py": "...",
#   "cdk/stacks/storage_stack.py": "...",
#   "cdk/stacks/__init__.py": "",
# }, "entry_point": "cdk/app.py", "metadata": {"stacks": [...], "services": [...]}}
```

Verify:
- One stack per brick (auth, events, storage)
- `app.py` imports and instantiates all stacks
- `requirements.txt` includes `aws-cdk-lib` and `constructs`
- No network stack (no VPC-requiring services)

### 4. Test VPC detection with Neptune

```python
vpc_specs = specs + [
    {"brick": "graph", "spec": {
        "service": "neptune", "construct": "DatabaseCluster",
        "props": {},
    }},
]

result = blueprint_validate_specs(specs=vpc_specs)
# Returns: {"valid": true, "vpc_required": true, ...}

result = blueprint_generate_cdk(specs=vpc_specs, project_name="my-service")
# Verify: "cdk/stacks/network_stack.py" is present in files
# Verify: network_stack appears first in metadata.stacks
```

### 5. Generate CI/CD pipeline

```python
result = blueprint_generate_pipeline(
    renderer="github_actions",
    project_name="my-service",
)
# Returns: {"project": "my-service", "renderer": "github_actions",
#   "files": {".github/workflows/deploy-infra.yml": "..."},
#   "metadata": {"stages": ["test", "synth", "deploy-staging", "deploy-prod"], "auth": "oidc"}}
```

Verify:
- OIDC auth configured (no hardcoded credentials)
- 4 stages: test → synth → deploy-staging → deploy-prod
- `cdk synth` runs in the synth job
- Artifacts uploaded between synth and deploy stages

### 6. Custom pipeline stages

```python
result = blueprint_generate_pipeline(
    renderer="github_actions",
    project_name="my-service",
    stages=["test", "synth", "deploy-staging"],
)
# Verify: only 3 stages, no deploy-prod
```

## Expected Outcomes

- ✅ Spec validation catches unsupported services
- ✅ CDK project has one stack per brick with correct L2 constructs
- ✅ VPC-requiring services trigger network stack generation
- ✅ IAM statements generated per service
- ✅ Pipeline uses OIDC auth, not hardcoded credentials
- ✅ Custom stages work correctly
