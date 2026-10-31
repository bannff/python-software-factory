"""CloudFormation operations for LocalStack sandbox.

Deploys, lists, and describes CFN stacks via the awscli sidecar.
Keeps the LocalStack adapter under 200 LOC by extracting CFN logic.
"""
from __future__ import annotations

import json
import logging
import tempfile
import time
from typing import Any

logger = logging.getLogger(__name__)

_AWS_PREFIX = (
    "AWS_DEFAULT_REGION=us-east-1 "
    "AWS_ACCESS_KEY_ID=test "
    "AWS_SECRET_ACCESS_KEY=test "
    "aws"
)


async def deploy_stack(
    execute_fn: Any,
    env_id: str,
    stack_name: str,
    template_body: str,
    parameters: dict[str, str] | None = None,
    capabilities: list[str] | None = None,
) -> dict[str, Any]:
    """Deploy a CFN stack to LocalStack via the awscli sidecar.

    Args:
        execute_fn: Async callable(env_id, command, timeout) -> dict.
        env_id: Sandbox environment ID.
        stack_name: CloudFormation stack name.
        template_body: YAML or JSON template content.
        parameters: Optional key-value parameter overrides.
        capabilities: IAM capabilities (default: CAPABILITY_NAMED_IAM).
    """
    caps = capabilities or ["CAPABILITY_NAMED_IAM"]
    caps_str = " ".join(caps)

    # Write template via base64 to avoid shell escaping issues
    import base64
    b64 = base64.b64encode(template_body.encode()).decode()
    write_cmd = f"echo '{b64}' | base64 -d > /tmp/{stack_name}.yaml"
    write_result = await execute_fn(env_id, write_cmd, 30)
    if write_result.get("exit_code", 1) != 0:
        return {"success": False, "error": f"Failed to write template: {write_result}"}

    # Build deploy command
    cmd = (
        f"{_AWS_PREFIX} cloudformation deploy"
        f" --template-file /tmp/{stack_name}.yaml"
        f" --stack-name {stack_name}"
        f" --capabilities {caps_str}"
        f" --no-fail-on-empty-changeset"
    )
    if parameters:
        overrides = " ".join(f"{k}={v}" for k, v in parameters.items())
        cmd += f" --parameter-overrides {overrides}"

    cmd += " 2>&1"
    t0 = time.monotonic()
    result = await execute_fn(env_id, cmd, 120)
    elapsed = int((time.monotonic() - t0) * 1000)

    success = result.get("exit_code", 1) == 0
    output: dict[str, Any] = {
        "success": success,
        "stack_name": stack_name,
        "stdout": result.get("stdout", ""),
        "stderr": result.get("stderr", ""),
        "duration_ms": elapsed,
    }

    # Fetch outputs if deploy succeeded
    if success:
        outputs = await describe_stack(execute_fn, env_id, stack_name)
        output["stack_outputs"] = outputs.get("outputs", {})
        output["stack_status"] = outputs.get("status", "UNKNOWN")

    return output


async def list_stacks(
    execute_fn: Any, env_id: str,
) -> dict[str, Any]:
    """List all CFN stacks in LocalStack."""
    cmd = (
        f"{_AWS_PREFIX} cloudformation list-stacks"
        " --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE"
        " CREATE_IN_PROGRESS UPDATE_IN_PROGRESS ROLLBACK_COMPLETE"
        " --query 'StackSummaries[].{Name:StackName,Status:StackStatus,Created:CreationTime}'"
        " --output json 2>&1"
    )
    result = await execute_fn(env_id, cmd, 30)
    if result.get("exit_code", 1) != 0:
        return {"stacks": [], "error": result.get("stdout", "")}
    try:
        stacks = json.loads(result.get("stdout", "[]"))
    except json.JSONDecodeError:
        stacks = []
    return {"stacks": stacks, "count": len(stacks)}


async def describe_stack(
    execute_fn: Any, env_id: str, stack_name: str,
) -> dict[str, Any]:
    """Describe a CFN stack — status, outputs, resources."""
    cmd = (
        f"{_AWS_PREFIX} cloudformation describe-stacks"
        f" --stack-name {stack_name}"
        " --output json 2>&1"
    )
    result = await execute_fn(env_id, cmd, 30)
    if result.get("exit_code", 1) != 0:
        return {"error": result.get("stdout", ""), "status": "NOT_FOUND"}
    try:
        data = json.loads(result.get("stdout", "{}"))
        stack = data.get("Stacks", [{}])[0]
    except (json.JSONDecodeError, IndexError):
        return {"error": "Failed to parse stack data", "status": "UNKNOWN"}

    outputs = {}
    for o in stack.get("Outputs", []):
        outputs[o.get("OutputKey", "")] = o.get("OutputValue", "")

    return {
        "stack_name": stack_name,
        "status": stack.get("StackStatus", "UNKNOWN"),
        "outputs": outputs,
        "creation_time": stack.get("CreationTime", ""),
        "description": stack.get("Description", ""),
    }


async def delete_stack(
    execute_fn: Any, env_id: str, stack_name: str,
) -> dict[str, Any]:
    """Delete a CFN stack from LocalStack."""
    cmd = (
        f"{_AWS_PREFIX} cloudformation delete-stack"
        f" --stack-name {stack_name} 2>&1"
    )
    result = await execute_fn(env_id, cmd, 60)
    success = result.get("exit_code", 1) == 0
    return {"success": success, "stack_name": stack_name}
