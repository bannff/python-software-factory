"""CFN-to-LocalStack translator — filter templates to supported resources.

Takes a full CloudFormation template (from CDK synth or hand-authored)
and strips it down to only the resources LocalStack can emulate.
Extracts the security-relevant attack surface for red team testing.

LocalStack supported services (ENFORCE_IAM=1):
  IAM, Lambda, S3, DynamoDB, SQS, SNS, API Gateway, CloudFormation,
  STS, SSM, KMS, Secrets Manager, CloudWatch Logs.
"""
from __future__ import annotations

import copy
import logging
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# Resource type prefixes that LocalStack supports
_SUPPORTED_PREFIXES = frozenset({
    "AWS::IAM::",
    "AWS::Lambda::",
    "AWS::S3::",
    "AWS::DynamoDB::",
    "AWS::SQS::",
    "AWS::SNS::",
    "AWS::ApiGateway::",
    "AWS::ApiGatewayV2::",
    "AWS::CloudFormation::",
    "AWS::SSM::",
    "AWS::KMS::",
    "AWS::SecretsManager::",
    "AWS::Logs::",
    "AWS::STS::",
    "AWS::Events::",
})

# Security-relevant resource types (subset of supported)
_SECURITY_RELEVANT = frozenset({
    "AWS::IAM::Role",
    "AWS::IAM::Policy",
    "AWS::IAM::ManagedPolicy",
    "AWS::IAM::User",
    "AWS::IAM::Group",
    "AWS::IAM::InstanceProfile",
    "AWS::S3::Bucket",
    "AWS::S3::BucketPolicy",
    "AWS::Lambda::Function",
    "AWS::Lambda::Permission",
    "AWS::DynamoDB::Table",
    "AWS::SQS::Queue",
    "AWS::SQS::QueuePolicy",
    "AWS::SNS::Topic",
    "AWS::SNS::TopicPolicy",
    "AWS::ApiGateway::RestApi",
    "AWS::ApiGateway::Method",
    "AWS::ApiGateway::Resource",
    "AWS::ApiGateway::Stage",
    "AWS::ApiGatewayV2::Api",
    "AWS::ApiGatewayV2::Route",
    "AWS::KMS::Key",
    "AWS::SecretsManager::Secret",
    "AWS::SSM::Parameter",
})


def is_supported(resource_type: str) -> bool:
    """Check if a CFN resource type is supported by LocalStack."""
    return any(resource_type.startswith(p) for p in _SUPPORTED_PREFIXES)


def is_security_relevant(resource_type: str) -> bool:
    """Check if a CFN resource type is security-relevant."""
    return resource_type in _SECURITY_RELEVANT


def translate(
    template_body: str,
    mode: str = "supported",
) -> dict[str, Any]:
    """Translate a CFN template to LocalStack-compatible subset.

    Args:
        template_body: YAML or JSON CFN template string.
        mode: 'supported' keeps all LocalStack-supported resources,
              'security' keeps only security-relevant ones.

    Returns:
        Dict with 'template' (filtered YAML string), 'kept' (list of
        kept resource logical IDs), 'dropped' (list of dropped ones),
        and 'stats' summary.
    """
    try:
        parsed = yaml.safe_load(template_body)
    except yaml.YAMLError as e:
        return {"error": f"Invalid YAML/JSON: {e}", "template": ""}

    if not isinstance(parsed, dict):
        return {"error": "Template must be a YAML/JSON mapping", "template": ""}

    resources = parsed.get("Resources", {})
    if not resources:
        return {"error": "No Resources section found", "template": ""}

    check_fn = is_security_relevant if mode == "security" else is_supported
    kept: list[str] = []
    dropped: list[str] = []
    filtered: dict[str, Any] = {}

    for logical_id, resource in resources.items():
        rtype = resource.get("Type", "")
        if check_fn(rtype):
            filtered[logical_id] = _clean_resource(resource)
            kept.append(logical_id)
        else:
            dropped.append(logical_id)

    # Rebuild template with only kept resources
    result = copy.deepcopy(parsed)
    result["Resources"] = filtered
    # Strip Outputs that reference dropped resources
    result["Outputs"] = _filter_outputs(
        result.get("Outputs", {}), set(kept),
    )
    # Remove Conditions/Mappings if empty after filtering
    for section in ("Conditions", "Mappings"):
        if section in result and not result[section]:
            del result[section]

    template_str = yaml.dump(result, default_flow_style=False, sort_keys=False)
    return {
        "template": template_str,
        "kept": kept,
        "dropped": dropped,
        "stats": {
            "total": len(resources),
            "kept": len(kept),
            "dropped": len(dropped),
            "mode": mode,
        },
    }


def _clean_resource(resource: dict[str, Any]) -> dict[str, Any]:
    """Clean a resource for LocalStack compatibility."""
    r = copy.deepcopy(resource)
    props = r.get("Properties", {})
    # Remove VPC-related props that LocalStack ignores
    for vpc_prop in ("VpcConfig", "SubnetIds", "SecurityGroupIds"):
        props.pop(vpc_prop, None)
    return r


def _filter_outputs(
    outputs: dict[str, Any], kept_ids: set[str],
) -> dict[str, Any]:
    """Keep only outputs that reference kept resources."""
    if not outputs:
        return {}
    filtered: dict[str, Any] = {}
    for key, val in outputs.items():
        # Simple heuristic: keep if any Ref/GetAtt references a kept resource
        val_str = str(val)
        if any(rid in val_str for rid in kept_ids):
            filtered[key] = val
    return filtered
