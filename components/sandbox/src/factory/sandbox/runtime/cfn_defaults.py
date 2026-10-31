"""Golden-default CFN template generation from discovered resource data.

Generates minimal CloudFormation templates for LocalStack deployment
when no CDK package exists. Uses resource metadata discovered by
environment discovery (DynamoDB tables, SQS queues, S3 buckets, Lambda
functions, IAM roles) to build reasonable defaults.

Each generator returns a CFN resource dict. The `build_cfn_template`
function assembles them into a complete template.
"""
from __future__ import annotations

from typing import Any

from .cfn_generators import EXTENDED_GENERATORS


def _ddb_resource(table_name: str, **kwargs: Any) -> dict:
    """Generate a DynamoDB table CFN resource with PAY_PER_REQUEST."""
    logical_id = table_name.replace(".", "").replace("-", "")
    return {
        logical_id: {
            "Type": "AWS::DynamoDB::Table",
            "Properties": {
                "TableName": table_name,
                "BillingMode": "PAY_PER_REQUEST",
                "AttributeDefinitions": [
                    {"AttributeName": "pk", "AttributeType": "S"},
                ],
                "KeySchema": [
                    {"AttributeName": "pk", "KeyType": "HASH"},
                ],
            },
        }
    }


def _sqs_resource(queue_name: str, **kwargs: Any) -> dict:
    """Generate an SQS queue CFN resource with defaults."""
    logical_id = queue_name.replace(".", "").replace("-", "")
    props: dict[str, Any] = {"QueueName": queue_name}
    if "DLQ" in queue_name or "dlq" in queue_name:
        props["MessageRetentionPeriod"] = 1209600  # 14 days
    return {logical_id: {"Type": "AWS::SQS::Queue", "Properties": props}}


def _s3_resource(bucket_name: str, **kwargs: Any) -> dict:
    """Generate an S3 bucket CFN resource."""
    logical_id = bucket_name.replace(".", "").replace("-", "")[:60]
    return {
        logical_id: {
            "Type": "AWS::S3::Bucket",
            "Properties": {"BucketName": bucket_name},
        }
    }


def _iam_role_resource(role_name: str, **kwargs: Any) -> dict:
    """Generate an IAM role CFN resource with basic trust."""
    logical_id = role_name.replace(".", "").replace("-", "")[:60]
    return {
        logical_id: {
            "Type": "AWS::IAM::Role",
            "Properties": {
                "RoleName": role_name,
                "AssumeRolePolicyDocument": {
                    "Version": "2012-10-17",
                    "Statement": [{
                        "Effect": "Allow",
                        "Principal": {"Service": "lambda.amazonaws.com"},
                        "Action": "sts:AssumeRole",
                    }],
                },
            },
        }
    }


_GENERATORS: dict[str, Any] = {
    "DynamoDB": _ddb_resource,
    "DynamoDBTable": _ddb_resource,  # backward compat alias
    "SQS": _sqs_resource,
    "S3": _s3_resource,
    "IamRole": _iam_role_resource,
    **EXTENDED_GENERATORS,
}


def build_cfn_template(
    resources: list[dict[str, Any]],
    description: str = "Auto-generated from discovered resources",
) -> dict[str, Any]:
    """Build a complete CFN template from a discovered resource list.

    Args:
        resources: List of dicts with 'type' and 'name' keys
            (as returned by the target-app resource discovery tool).
        description: Template description.

    Returns:
        Complete CFN template dict ready for sandbox_deploy_cfn.
    """
    cfn_resources: dict[str, Any] = {}
    for res in resources:
        rtype = res.get("type", "")
        name = res.get("name", "")
        if not name or not rtype:
            continue
        gen = _GENERATORS.get(rtype)
        if gen:
            cfn_resources.update(gen(name))

    return {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Description": description,
        "Resources": cfn_resources,
    }
