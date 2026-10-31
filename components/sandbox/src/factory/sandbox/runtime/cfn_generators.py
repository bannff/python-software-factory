"""Extended CFN resource generators for LocalStack deployment.

Generators for resource types beyond the core set (DynamoDB, SQS,
S3, IAM). Each returns a CFN resource dict keyed by logical ID.
"""
from __future__ import annotations

from typing import Any


def _lambda_resource(name: str, **kwargs: Any) -> dict:
    """Generate a Lambda function CFN resource with inline handler."""
    logical_id = name.replace(".", "").replace("-", "")[:60]
    return {
        logical_id: {
            "Type": "AWS::Lambda::Function",
            "Properties": {
                "FunctionName": name,
                "Runtime": "python3.12",
                "Handler": "index.handler",
                "Role": "arn:aws:iam::000000000000:role/lambda-role",
                "Code": {"ZipFile": (
                    "def handler(event, context):\n"
                    "    return {'statusCode': 200, "
                    "'body': 'mock'}\n"
                )},
            },
        }
    }


def _sns_resource(name: str, **kwargs: Any) -> dict:
    """Generate an SNS topic CFN resource."""
    logical_id = name.replace(".", "").replace("-", "")[:60]
    return {
        logical_id: {
            "Type": "AWS::SNS::Topic",
            "Properties": {"TopicName": name},
        }
    }


def _ecs_cluster_resource(name: str, **kwargs: Any) -> dict:
    """Generate an ECS cluster CFN resource."""
    logical_id = name.replace(".", "").replace("-", "")[:60]
    return {
        logical_id: {
            "Type": "AWS::ECS::Cluster",
            "Properties": {"ClusterName": name},
        }
    }


def _api_gateway_resource(name: str, **kwargs: Any) -> dict:
    """Generate an API Gateway REST API CFN resource."""
    logical_id = name.replace(".", "").replace("-", "")[:60]
    return {
        logical_id: {
            "Type": "AWS::ApiGateway::RestApi",
            "Properties": {"Name": name},
        }
    }


def _kms_resource(name: str, **kwargs: Any) -> dict:
    """Generate a KMS key CFN resource with basic policy."""
    logical_id = name.replace(".", "").replace("-", "")[:60]
    return {
        logical_id: {
            "Type": "AWS::KMS::Key",
            "Properties": {
                "Description": name,
                "KeyPolicy": {
                    "Version": "2012-10-17",
                    "Statement": [{
                        "Effect": "Allow",
                        "Principal": {"AWS": "*"},
                        "Action": "kms:*",
                        "Resource": "*",
                    }],
                },
            },
        }
    }


def _secret_resource(name: str, **kwargs: Any) -> dict:
    """Generate a Secrets Manager secret CFN resource."""
    logical_id = name.replace(".", "").replace("-", "")[:60]
    return {
        logical_id: {
            "Type": "AWS::SecretsManager::Secret",
            "Properties": {
                "Name": name,
                "SecretString": "{}",
            },
        }
    }


def _ssm_parameter_resource(name: str, **kwargs: Any) -> dict:
    """Generate an SSM Parameter Store CFN resource."""
    logical_id = name.replace(".", "").replace("-", "")[:60]
    return {
        logical_id: {
            "Type": "AWS::SSM::Parameter",
            "Properties": {
                "Name": name,
                "Type": "String",
                "Value": "placeholder",
            },
        }
    }


EXTENDED_GENERATORS: dict[str, Any] = {
    "Lambda": _lambda_resource,
    "SNS": _sns_resource,
    "ECSCluster": _ecs_cluster_resource,
    "ApiGateway": _api_gateway_resource,
    "ApiGatewayMethod": _api_gateway_resource,
    "KMS": _kms_resource,
    "Secret": _secret_resource,
    "SSMParameter": _ssm_parameter_resource,
}
