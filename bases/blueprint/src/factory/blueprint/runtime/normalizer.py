"""Spec normalizer — converts 3 infrastructure_spec() shapes to NormalizedResource.

Shape 1 (flat): {"service": "dynamodb", "construct": "Table", "props": {...}}
Shape 2 (CFN):  {"provider": "aws", "resources": [{"type": "AWS::Cognito::UserPool", "properties": {...}}]}
Shape 3 (list): {"services": [{"service": "sns", "construct": "Topic", "props": {...}}]}
"""

from __future__ import annotations

from typing import Any

from .ports import NormalizedResource

# CloudFormation type → (service, construct) mapping
_CFN_TYPE_MAP: dict[str, tuple[str, str]] = {
    "AWS::DynamoDB::Table": ("dynamodb", "Table"),
    "AWS::S3::Bucket": ("s3", "Bucket"),
    "AWS::SQS::Queue": ("sqs", "Queue"),
    "AWS::SNS::Topic": ("sns", "Topic"),
    "AWS::Cognito::UserPool": ("cognito-idp", "UserPool"),
    "AWS::Cognito::UserPoolClient": ("cognito-idp", "UserPoolClient"),
    "AWS::Lambda::Function": ("lambda", "Function"),
    "AWS::StepFunctions::StateMachine": ("stepfunctions", "StateMachine"),
    "AWS::ElastiCache::CacheCluster": ("elasticache", "CfnCacheCluster"),
    "AWS::Neptune::DBCluster": ("neptune", "DatabaseCluster"),
    "AWS::RDS::DBCluster": ("aurora-serverless", "ServerlessCluster"),
    "AWS::Kinesis::Stream": ("kinesis", "Stream"),
    "AWS::Events::EventBus": ("eventbridge", "EventBus"),
    "AWS::ApiGateway::RestApi": ("apigateway", "RestApi"),
    "AWS::SecretsManager::Secret": ("secretsmanager", "Secret"),
    "AWS::SES::EmailIdentity": ("ses", "EmailIdentity"),
}


def normalize_spec(brick: str, raw: dict[str, Any]) -> list[NormalizedResource]:
    """Normalize an infrastructure_spec() dict into NormalizedResource list.

    Detects which of the 3 shapes the spec uses and normalizes accordingly.
    """
    if "resources" in raw:
        return _normalize_cfn_shape(brick, raw)
    if "services" in raw:
        return _normalize_list_shape(brick, raw)
    if "service" in raw and "construct" in raw:
        return [_normalize_flat_shape(brick, raw)]
    return []


def _normalize_flat_shape(brick: str, raw: dict[str, Any]) -> NormalizedResource:
    """Shape 1: flat single-resource spec."""
    service = raw["service"]
    construct = raw["construct"]
    props = raw.get("props", {})
    logical_id = _make_logical_id(brick, service, construct)
    return NormalizedResource(
        brick=brick, service=service, construct=construct,
        props=props, logical_id=logical_id,
    )


def _normalize_cfn_shape(brick: str, raw: dict[str, Any]) -> list[NormalizedResource]:
    """Shape 2: CloudFormation-style resources list."""
    results: list[NormalizedResource] = []
    for res in raw.get("resources", []):
        cfn_type = res.get("type", "")
        mapping = _CFN_TYPE_MAP.get(cfn_type)
        if not mapping:
            continue
        service, construct = mapping
        props = res.get("properties", {})
        logical_id = _make_logical_id(brick, service, construct)
        results.append(NormalizedResource(
            brick=brick, service=service, construct=construct,
            props=props, logical_id=logical_id,
        ))
    return results


def _normalize_list_shape(brick: str, raw: dict[str, Any]) -> list[NormalizedResource]:
    """Shape 3: services list spec."""
    results: list[NormalizedResource] = []
    for svc in raw.get("services", []):
        results.append(_normalize_flat_shape(brick, svc))
    return results


def _make_logical_id(brick: str, service: str, construct: str) -> str:
    """Generate a logical ID like 'StorageDynamodbTable'."""
    parts = [
        brick.replace("-", "_").replace("_", " ").title().replace(" ", ""),
        service.replace("-", "_").replace("_", " ").title().replace(" ", ""),
        construct,
    ]
    return "".join(parts)
