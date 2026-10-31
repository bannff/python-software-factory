"""Blueprint core — shared constants and CDK service mappings.

Maps AWS service names to CDK module + construct pairs used by the
CDK renderer to generate L2 construct code.
"""

from __future__ import annotations

# AWS service → (cdk_module, default_construct, import_alias)
SERVICE_CDK_MODULES: dict[str, tuple[str, str, str]] = {
    "dynamodb": ("aws_cdk.aws_dynamodb", "Table", "dynamodb"),
    "s3": ("aws_cdk.aws_s3", "Bucket", "s3"),
    "sqs": ("aws_cdk.aws_sqs", "Queue", "sqs"),
    "sns": ("aws_cdk.aws_sns", "Topic", "sns"),
    "ses": ("aws_cdk.aws_ses", "EmailIdentity", "ses"),
    "cognito-idp": ("aws_cdk.aws_cognito", "UserPool", "cognito"),
    "lambda": ("aws_cdk.aws_lambda", "Function", "lambda_"),
    "stepfunctions": ("aws_cdk.aws_stepfunctions", "StateMachine", "sfn"),
    "elasticache": ("aws_cdk.aws_elasticache", "CfnCacheCluster", "elasticache"),
    "neptune": ("aws_cdk.aws_neptune", "DatabaseCluster", "neptune"),
    "aurora-serverless": ("aws_cdk.aws_rds", "ServerlessCluster", "rds"),
    "kinesis": ("aws_cdk.aws_kinesis", "Stream", "kinesis"),
    "eventbridge": ("aws_cdk.aws_events", "EventBus", "events"),
    "apigateway": ("aws_cdk.aws_apigateway", "RestApi", "apigw"),
    "secretsmanager": ("aws_cdk.aws_secretsmanager", "Secret", "secretsmanager"),
}

# Services that require VPC networking
VPC_REQUIRED_SERVICES: set[str] = {
    "neptune",
    "elasticache",
    "aurora-serverless",
}

# IAM action prefixes per service
SERVICE_IAM_ACTIONS: dict[str, list[str]] = {
    "dynamodb": ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:Query",
                  "dynamodb:DeleteItem", "dynamodb:UpdateItem"],
    "s3": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"],
    "sqs": ["sqs:SendMessage", "sqs:ReceiveMessage", "sqs:DeleteMessage"],
    "sns": ["sns:Publish", "sns:Subscribe"],
    "ses": ["ses:SendEmail"],
    "cognito-idp": ["cognito-idp:AdminInitiateAuth", "cognito-idp:AdminGetUser"],
    "lambda": ["lambda:InvokeFunction"],
    "stepfunctions": ["states:StartExecution", "states:DescribeExecution"],
    "kinesis": ["kinesis:PutRecord", "kinesis:GetRecords"],
    "eventbridge": ["events:PutEvents"],
    "secretsmanager": ["secretsmanager:GetSecretValue"],
    "neptune": ["neptune-db:*"],
    "elasticache": ["elasticache:*"],
    "aurora-serverless": ["rds-data:ExecuteStatement", "rds-data:BatchExecuteStatement"],
    "apigateway": ["execute-api:Invoke"],
}
