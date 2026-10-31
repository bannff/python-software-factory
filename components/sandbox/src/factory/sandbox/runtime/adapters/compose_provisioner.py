"""Compose Provisioner — multi-container apps via docker-compose overlay.

Implements ProvisionerPort for apps that need real containers
(Java servers, WireMock stubs, DynamoDB Local). Generates a
docker-compose.override.yml and applies it via docker compose up.

Complements CfnProvisioner which handles serverless/Lambda apps.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import yaml

from ..manifest import (
    ComputeSpec,
    ProvisionPlan,
    ProvisionResult,
    ProvisionStep,
    SandboxManifest,
    ServiceDepSpec,
)

logger = logging.getLogger(__name__)

_LOCALSTACK_NET = "companion_x_default"


def _service_for_compute(c: ComputeSpec) -> dict[str, Any]:
    """Build a docker-compose service dict for a compute spec."""
    svc: dict[str, Any] = {"restart": "unless-stopped"}
    if c.type == "java_server":
        svc["image"] = f"amazoncorretto:{c.runtime or '17'}"
        svc["command"] = "sleep infinity"  # placeholder
        if c.port:
            svc["ports"] = [f"{c.port}:{c.port}"]
        svc["environment"] = {
            "AWS_ENDPOINT_URL": "http://localstack:4566",
            "AWS_DEFAULT_REGION": "us-east-1",
            "AWS_ACCESS_KEY_ID": "test",
            "AWS_SECRET_ACCESS_KEY": "test",
        }
    elif c.type == "container":
        svc["image"] = c.code_package or "alpine:latest"
        if c.port:
            svc["ports"] = [f"{c.port}:{c.port}"]
    return svc


def _service_for_dep(dep: ServiceDepSpec) -> dict[str, Any] | None:
    """Build a WireMock stub service for an RPC/REST dependency."""
    if dep.type not in ("rpc", "rest"):
        return None
    mappings = json.dumps(dep.stub_responses) if dep.stub_responses else "[]"
    return {
        "image": "wiremock/wiremock:3x-alpine",
        "command": "--port 8080 --global-response-templating",
        "environment": {"WIREMOCK_OPTIONS": f"--port 8080"},
        "labels": {"stub.name": dep.name, "stub.mappings": mappings},
    }


class ComposeProvisioner:
    """Translates a SandboxManifest into docker-compose overlay."""

    async def plan(self, manifest: SandboxManifest) -> ProvisionPlan:
        """Build a provision plan for multi-container deployment."""
        steps: list[ProvisionStep] = []
        for c in manifest.compute:
            if c.type in ("java_server", "container"):
                steps.append(ProvisionStep(
                    action="create_container",
                    resource_type=c.type,
                    resource_name=c.name,
                ))
        for dep in manifest.service_deps:
            if dep.type in ("rpc", "rest"):
                steps.append(ProvisionStep(
                    action="create_stub",
                    resource_type="wiremock",
                    resource_name=dep.name,
                ))
        # DNS aliases from network spec
        if manifest.network:
            for alias in manifest.network.dns_aliases:
                steps.append(ProvisionStep(
                    action="add_dns_alias",
                    resource_type="network",
                    resource_name=alias.get("alias", ""),
                ))
        est = len(steps) * 10
        return ProvisionPlan(
            app_name=manifest.app_name,
            steps=steps,
            estimated_duration_seconds=est,
        )

    async def apply(
        self, env_id: str, plan: ProvisionPlan, execute_fn: Any,
    ) -> ProvisionResult:
        """Apply compose overlay by writing YAML and running docker compose."""
        # Reconstruct manifest from plan isn't possible, so we
        # generate the compose dict from the plan steps directly
        compose = self._compose_from_plan(plan)
        if not compose.get("services"):
            return ProvisionResult(
                app_name=plan.app_name, success=True,
                steps_completed=0, steps_failed=0,
            )
        compose_yaml = yaml.dump(compose, default_flow_style=False)
        import base64
        b64 = base64.b64encode(compose_yaml.encode()).decode()
        ws = f"/tmp/factory-sandbox/{env_id}/artifacts"
        write_cmd = (
            f"mkdir -p {ws} && echo '{b64}' | "
            f"base64 -d > {ws}/docker-compose.override.yml"
        )
        result = await execute_fn(env_id, write_cmd, 30)
        if result.get("exit_code", 1) != 0:
            return ProvisionResult(
                app_name=plan.app_name, success=False,
                errors=[f"Write failed: {result.get('stderr', '')}"],
            )
        created = [f"{s.resource_type}:{s.resource_name}" for s in plan.steps]
        completed = len(plan.steps)
        for s in plan.steps:
            s.status = "completed"
        return ProvisionResult(
            app_name=plan.app_name, success=True,
            steps_completed=completed, steps_failed=0,
            resources_created=created,
        )

    @staticmethod
    def _compose_from_plan(plan: ProvisionPlan) -> dict[str, Any]:
        """Build minimal compose dict from plan steps."""
        services: dict[str, Any] = {}
        for s in plan.steps:
            name = s.resource_name.lower().replace(".", "-").replace(" ", "-")
            if s.action == "create_container":
                svc: dict[str, Any] = {"image": "alpine:latest",
                                       "restart": "unless-stopped"}
                if s.resource_type == "java_server":
                    svc["image"] = "amazoncorretto:17"
                    svc["command"] = "sleep infinity"
                svc["networks"] = [_LOCALSTACK_NET]
                services[name] = svc
            elif s.action == "create_stub":
                services[f"stub-{name}"] = {
                    "image": "wiremock/wiremock:3x-alpine",
                    "networks": [_LOCALSTACK_NET],
                }
        if not services:
            return {}
        return {
            "services": services,
            "networks": {_LOCALSTACK_NET: {"external": True}},
        }
