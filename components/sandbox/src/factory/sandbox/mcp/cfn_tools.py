"""Typed CloudFormation MCP tools for the Sandbox brick."""
from __future__ import annotations

import json as _json
from typing import TYPE_CHECKING, Any

from pydantic import Field

from factory.mcp_utils.interface import ok, operational
from factory.mcp_utils.runtime.tool_result import ToolResult
from .cfn_models import (
    DeleteStackResult, DeployStackRequest, DeployStackResult,
    EnvOnlyRequest, StackDescriptionResult, StackListResult, StackRequest,
    TranslateCfnRequest, TranslateCfnResult,
)

if TYPE_CHECKING:
    from ..runtime.runtime import SandboxRuntime

_AWS_PREFIX = (
    "AWS_DEFAULT_REGION=us-east-1 AWS_ACCESS_KEY_ID=test "
    "AWS_SECRET_ACCESS_KEY=test aws --endpoint-url=http://localhost:4566"
)


def _aws_cmd(base: str) -> str:
    """Build a full AWS CLI command with LocalStack environment variables."""
    return f"{_AWS_PREFIX} {base}"


def _parse_json(text: Any) -> Any:
    """Parse JSON strings while retaining non-JSON values."""
    if text is None:
        return None
    try:
        return _json.loads(text)
    except (ValueError, TypeError):
        return text


async def _find_localstack_env(runtime: "SandboxRuntime") -> str | None:
    """Find the first LocalStack environment."""
    for environment in runtime.list_environments():
        if "localstack" in environment.env_id.lower():
            return environment.env_id
    return None


def register(mcp: Any, runtime: "SandboxRuntime") -> None:
    """Register typed CloudFormation operations."""

    @mcp.tool(name="sandbox.deploy_cfn")
    @operational(input_model=DeployStackRequest, output_model=DeployStackResult)
    async def deploy_cfn(
        env_id: str = Field(min_length=1, max_length=256),
        stack_name: str = Field(min_length=1, max_length=128),
        template_body: str = Field(min_length=1, max_length=1_000_000),
        parameters: dict[str, str] | None = None,
        capabilities: list[str] | None = None,
    ) -> ToolResult[DeployStackResult]:
        """Deploy a CloudFormation template to a sandbox."""
        return ok(DeployStackResult.model_validate(await runtime.deploy_stack(
            env_id, stack_name, template_body, parameters, capabilities,
        )))

    @mcp.tool(name="sandbox.list_stacks")
    @operational(input_model=EnvOnlyRequest, output_model=StackListResult)
    async def list_stacks(env_id: str = Field(min_length=1, max_length=256)) -> ToolResult[StackListResult]:
        """List CloudFormation stacks in a sandbox."""
        return ok(StackListResult.model_validate(await runtime.list_stacks(env_id)))

    @mcp.tool(name="sandbox.describe_stack")
    @operational(input_model=StackRequest, output_model=StackDescriptionResult)
    async def describe_stack(
        env_id: str = Field(min_length=1, max_length=256),
        stack_name: str = Field(min_length=1, max_length=128),
    ) -> ToolResult[StackDescriptionResult]:
        """Describe one CloudFormation stack."""
        return ok(StackDescriptionResult.model_validate(await runtime.describe_stack(env_id, stack_name)))

    @mcp.tool(name="sandbox.delete_stack")
    @operational(input_model=StackRequest, output_model=DeleteStackResult)
    async def delete_stack(
        env_id: str = Field(min_length=1, max_length=256),
        stack_name: str = Field(min_length=1, max_length=128),
    ) -> ToolResult[DeleteStackResult]:
        """Delete one CloudFormation stack."""
        return ok(DeleteStackResult.model_validate(await runtime.delete_stack(env_id, stack_name)))

    @mcp.tool(name="sandbox.translate_cfn")
    @operational(input_model=TranslateCfnRequest, output_model=TranslateCfnResult)
    def translate_cfn(
        template_body: str = Field(min_length=1, max_length=1_000_000),
        mode: str = Field(default="supported", pattern="^(supported|security)$"),
    ) -> ToolResult[TranslateCfnResult]:
        """Translate CFN into the LocalStack-supported subset."""
        from ..runtime.cfn_translator import translate
        return ok(TranslateCfnResult.model_validate(translate(template_body, mode)))
