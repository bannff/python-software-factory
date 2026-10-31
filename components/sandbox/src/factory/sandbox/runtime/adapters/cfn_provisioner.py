"""CFN Provisioner — translates SandboxManifest to LocalStack CFN.

Implements ProvisionerPort for serverless/Lambda apps. Converts
manifest data stores and compute specs into CFN resources using
the existing cfn_defaults generators, then deploys via cfn_ops.
"""
from __future__ import annotations

import logging
from typing import Any

from ..manifest import (
    ProvisionPlan,
    ProvisionResult,
    ProvisionStep,
    SandboxManifest,
)

logger = logging.getLogger(__name__)

# Map manifest data store types to cfn_defaults resource types
_STORE_TYPE_MAP: dict[str, str] = {
    "dynamodb": "DynamoDB",
    "s3": "S3",
    "sqs": "SQS",
    "sns": "SNS",
    "kms": "KMS",
    "secret": "Secret",
    "ssm": "SSMParameter",
}

# Map manifest compute types to cfn_defaults resource types
_COMPUTE_TYPE_MAP: dict[str, str] = {
    "lambda": "Lambda",
    "ecs": "ECSCluster",
}


class CfnProvisioner:
    """Translates a SandboxManifest into CFN and deploys to LocalStack."""

    async def plan(self, manifest: SandboxManifest) -> ProvisionPlan:
        """Build a provision plan from the manifest."""
        steps: list[ProvisionStep] = []

        # 1. Data stores → CFN resources
        for ds in manifest.data_stores:
            steps.append(ProvisionStep(
                action="create_resource",
                resource_type=_STORE_TYPE_MAP.get(ds.type, ds.type),
                resource_name=ds.name,
            ))

        # 2. Compute → CFN resources (Lambda/ECS only)
        for c in manifest.compute:
            cfn_type = _COMPUTE_TYPE_MAP.get(c.type)
            if cfn_type:
                steps.append(ProvisionStep(
                    action="create_resource",
                    resource_type=cfn_type,
                    resource_name=c.name,
                ))

        # 3. Pre-built CFN template (from CDK synth or manual)
        if manifest.cfn_template:
            steps.append(ProvisionStep(
                action="deploy_cfn",
                resource_type="CloudFormation",
                resource_name=f"{manifest.app_name}-custom",
                command=manifest.cfn_template,
            ))

        # 4. Init scripts
        for script in manifest.init_scripts:
            steps.append(ProvisionStep(
                action="run_script",
                resource_type="script",
                resource_name=script[:60],
                command=script,
            ))

        est = len(steps) * 5  # ~5s per step
        return ProvisionPlan(
            app_name=manifest.app_name,
            steps=steps,
            estimated_duration_seconds=est,
        )

    async def apply(
        self,
        env_id: str,
        plan: ProvisionPlan,
        execute_fn: Any,
    ) -> ProvisionResult:
        """Execute a provision plan against a LocalStack sandbox."""
        from ..cfn_defaults import build_cfn_template
        from .cfn_ops import deploy_stack

        created: list[str] = []
        errors: list[str] = []
        completed = 0
        failed = 0

        # Batch CFN-deployable resources into a single stack
        cfn_resources = [
            {"type": s.resource_type, "name": s.resource_name}
            for s in plan.steps if s.action == "create_resource"
        ]
        if cfn_resources:
            template = build_cfn_template(
                cfn_resources,
                description=f"Provisioned from manifest: {plan.app_name}",
            )
            import json
            result = await deploy_stack(
                execute_fn, env_id,
                f"{plan.app_name}-infra",
                json.dumps(template),
            )
            if result.get("success"):
                for r in cfn_resources:
                    created.append(f"{r['type']}:{r['name']}")
                    completed += 1
                # Mark resource steps done
                for s in plan.steps:
                    if s.action == "create_resource":
                        s.status = "completed"
            else:
                err = result.get("stderr", result.get("stdout", "unknown"))
                errors.append(f"CFN deploy failed: {err}")
                failed += len(cfn_resources)
                for s in plan.steps:
                    if s.action == "create_resource":
                        s.status = "failed"

        # Deploy custom CFN templates
        for s in plan.steps:
            if s.action != "deploy_cfn":
                continue
            result = await deploy_stack(
                execute_fn, env_id, s.resource_name, s.command,
            )
            if result.get("success"):
                created.append(f"Stack:{s.resource_name}")
                s.status = "completed"
                completed += 1
            else:
                err = result.get("stderr", result.get("stdout", ""))
                errors.append(f"Stack {s.resource_name}: {err}")
                s.status = "failed"
                failed += 1

        # Run init scripts
        for s in plan.steps:
            if s.action != "run_script":
                continue
            result = await execute_fn(env_id, s.command, 120)
            if result.get("exit_code", 1) == 0:
                s.status = "completed"
                completed += 1
            else:
                err = result.get("stderr", result.get("stdout", ""))
                errors.append(f"Script failed: {err}")
                s.status = "failed"
                failed += 1

        return ProvisionResult(
            app_name=plan.app_name,
            success=failed == 0,
            steps_completed=completed,
            steps_failed=failed,
            resources_created=created,
            errors=errors,
        )
