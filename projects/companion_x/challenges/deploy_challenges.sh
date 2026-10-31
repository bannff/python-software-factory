#!/bin/bash
# Deploy all challenge CloudFormation templates into LocalStack.
# Idempotent — re-running won't fail.
set -euo pipefail

AWS="aws --endpoint-url http://localhost:4566 --region us-east-1"

echo "Deploying IAM privesc challenge..."
$AWS cloudformation deploy \
  --template-file /challenges/iam-privesc/template.yaml \
  --stack-name iam-privesc \
  --capabilities CAPABILITY_NAMED_IAM \
  --no-fail-on-empty-changeset 2>/dev/null || true

echo "Deploying SSRF Lambda challenge..."
$AWS cloudformation deploy \
  --template-file /challenges/ssrf-lambda/template.yaml \
  --stack-name ssrf-lambda \
  --capabilities CAPABILITY_NAMED_IAM \
  --no-fail-on-empty-changeset 2>/dev/null || true

echo "Deploying IDOR Warehouse challenge..."
$AWS cloudformation deploy \
  --template-file /challenges/idor-warehouse/template.yaml \
  --stack-name idor-warehouse \
  --capabilities CAPABILITY_NAMED_IAM \
  --no-fail-on-empty-changeset 2>/dev/null || true

echo "Seeding test data..."
echo '{"secret":"do-not-expose"}' | $AWS s3 cp - s3://example-bucket/sensitive.json 2>/dev/null || true

echo "Verifying deployments..."
$AWS cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
  --query 'StackSummaries[].StackName' --output text

echo "Done."
