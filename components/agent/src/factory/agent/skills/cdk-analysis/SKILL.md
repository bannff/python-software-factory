---
name: cdk-analysis
description: Read and analyze CDK infrastructure code from repository packages to find misconfigurations and secrets.
---
# CDK Infrastructure Analysis

You are analyzing CDK (Cloud Development Kit) infrastructure code.

## Builder Tools


## Priority Files to Review

1. `lib/stages.ts` — stage configs, often contains hardcoded ARNs/secrets
2. `lib/app.ts` — CDK app definition, pipeline config
3. `lib/ecs_service.ts` — service definitions, IAM roles
4. `lib/vpc.ts` — network config, security groups
5. `cdk.json` — CDK context, feature flags
6. `package.json` — dependencies, scripts

## What to Look For

- Hardcoded credentials (AWS keys, passwords, tokens)
- Overpermissive IAM policies (Action:*, Resource:*)
- Unencrypted resources (S3, DynamoDB, RDS)
- Public endpoints without auth
- Missing logging/monitoring
- Cross-account trust relationships

## Graph Modeling

For each resource found, create a graph entity:
```
graph_add_entity(entity_id='<type>-<name>', entity_type='<Type>',
    properties={...relevant fields...})
```

Types: TargetApp, AWSAccount, IAMRole, S3Bucket, DynamoDBTable,
APIGateway, Lambda, SecretsManager, KMSKey

Connect with relationships:
```
graph_add_relationship(source_id=..., target_id=...,
    relationship_type='OWNS|ACCESSES|ATTACK_PATH')
```
