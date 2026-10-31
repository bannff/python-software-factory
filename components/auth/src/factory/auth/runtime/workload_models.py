"""Strict provider-neutral workload credential contracts."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from factory.mcp_utils.interface import canonical_scope_digest

_SHA256 = re.compile(r"[0-9a-f]{64}")
_TOOL = re.compile(r"[a-z][a-z0-9]*(?:[._][a-z0-9]+)*")
_META = frozenset({
    "call_brick_tool", "get_brick_tools", "get_brick_resources",
    "get_brick_prompts", "get_tool_catalog", "list_bricks",
    "read_brick_resource", "render_brick_prompt",
})


class FrozenStrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    @field_validator("launch_id", check_fields=False)
    @classmethod
    def _launch_id(cls, value: str) -> str:
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", value) is None:
            raise ValueError("launch_id is malformed")
        return value


def canonical_grant_manifest_digest(
    *, launch_id: str, generation: int, tenant_id: str, audience: str,
    allowed_tools: Iterable[str], policy_id: str,
    capability_scope_digest: str, ttl_seconds: int,
) -> str:
    """Bind every immutable grant authority field into one canonical digest."""
    payload = {
        "allowed_tools": sorted(allowed_tools), "audience": audience,
        "capability_scope_digest": capability_scope_digest,
        "generation": generation, "launch_id": launch_id,
        "policy_id": policy_id, "tenant_id": tenant_id,
        "ttl_seconds": ttl_seconds,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


class WorkloadGrant(FrozenStrictModel):
    launch_id: str = Field(min_length=1, max_length=128)
    generation: int = Field(ge=1)
    tenant_id: str = Field(min_length=1, max_length=128)
    audience: str = Field(min_length=1, max_length=256)
    allowed_tools: list[str] = Field(min_length=1, max_length=128)
    policy_id: str = Field(min_length=1, max_length=137)
    capability_scope_digest: str
    manifest_digest: str
    ttl_seconds: Literal[300] = 300

    @classmethod
    def create(cls, *, launch_id: str, generation: int, tenant_id: str,
               audience: str, allowed_tools: Iterable[str]) -> "WorkloadGrant":
        """Freeze a valid launch-bound grant without caller-authored hashes."""
        tools = sorted(allowed_tools)
        policy_id = f"workload:{launch_id}"
        scope_digest = canonical_scope_digest(policy_id, tools, 0)
        manifest_digest = canonical_grant_manifest_digest(
            launch_id=launch_id, generation=generation, tenant_id=tenant_id,
            audience=audience, allowed_tools=tools, policy_id=policy_id,
            capability_scope_digest=scope_digest, ttl_seconds=300,
        )
        return cls(
            launch_id=launch_id, generation=generation, tenant_id=tenant_id,
            audience=audience, allowed_tools=tools, policy_id=policy_id,
            capability_scope_digest=scope_digest,
            manifest_digest=manifest_digest, ttl_seconds=300,
        )

    @field_validator("capability_scope_digest", "manifest_digest")
    @classmethod
    def _digest(cls, value: str) -> str:
        if _SHA256.fullmatch(value) is None:
            raise ValueError("digest must be a lowercase SHA-256 digest")
        return value

    @field_validator("allowed_tools")
    @classmethod
    def _tools(cls, values: list[str]) -> list[str]:
        if values != sorted(values) or len(values) != len(set(values)):
            raise ValueError("allowed_tools must be sorted and unique")
        for name in values:
            lowered = name.lower()
            if _TOOL.fullmatch(name) is None or not ({"_", "."} & set(name)) \
                    or name.startswith(("brick.", "brick_")):
                raise ValueError("allowed_tools must contain exact canonical leaf names")
            if name in _META or "authoring" in lowered or lowered.startswith("auth") \
                    or "token" in lowered or "credential" in lowered:
                raise ValueError("allowed_tools contains a forbidden control-plane tool")
        return values

    @model_validator(mode="after")
    def _authority_binding(self) -> "WorkloadGrant":
        if self.policy_id != f"workload:{self.launch_id}":
            raise ValueError("workload policy must be launch-bound")
        expected_scope = canonical_scope_digest(self.policy_id, self.allowed_tools, 0)
        if self.capability_scope_digest != expected_scope:
            raise ValueError("workload capability scope digest mismatch")
        expected_manifest = canonical_grant_manifest_digest(**self.model_dump(
            exclude={"manifest_digest"}))
        if self.manifest_digest != expected_manifest:
            raise ValueError("workload manifest digest mismatch")
        return self


class AccessCredential(FrozenStrictModel):
    credential_id: str = Field(min_length=1, max_length=128)
    subject: str = Field(min_length=1, max_length=256)
    actor_type: Literal["workload"] = "workload"
    role: Literal["workload"] = "workload"
    tenant_id: str = Field(min_length=1, max_length=128)
    audience: str = Field(min_length=1, max_length=256)
    scopes: tuple[str, ...] = Field(min_length=1)
    allowed_tools: tuple[str, ...] = Field(min_length=1)
    policy_id: str = Field(min_length=1, max_length=137)
    capability_scope_digest: str
    manifest_digest: str
    launch_id: str = Field(min_length=1, max_length=128)
    generation: int = Field(ge=1)
    issued_at: int
    expires_at: int

    @field_validator("capability_scope_digest", "manifest_digest")
    @classmethod
    def _credential_digest(cls, value: str) -> str:
        if _SHA256.fullmatch(value) is None:
            raise ValueError("digest must be a lowercase SHA-256 digest")
        return value

    @model_validator(mode="after")
    def _exact_binding(self) -> "AccessCredential":
        tools = list(self.allowed_tools)
        WorkloadGrant._tools(tools)
        if self.subject != f"svc:squad:{self.launch_id}":
            raise ValueError("workload subject must be server-derived from launch_id")
        if self.scopes != self.allowed_tools:
            raise ValueError("workload scopes and allowed_tools must match exactly")
        if self.policy_id != f"workload:{self.launch_id}":
            raise ValueError("workload policy must be launch-bound")
        if self.capability_scope_digest != canonical_scope_digest(self.policy_id, tools, 0):
            raise ValueError("workload capability scope digest mismatch")
        expected_manifest = canonical_grant_manifest_digest(
            launch_id=self.launch_id, generation=self.generation,
            tenant_id=self.tenant_id, audience=self.audience,
            allowed_tools=tools, policy_id=self.policy_id,
            capability_scope_digest=self.capability_scope_digest, ttl_seconds=300,
        )
        if self.manifest_digest != expected_manifest:
            raise ValueError("workload manifest digest mismatch")
        if self.expires_at - self.issued_at != 300:
            raise ValueError("workload credential TTL must be exactly 300 seconds")
        return self


class IssuedWorkloadCredential(FrozenStrictModel):
    credential: AccessCredential
    access_token: str = Field(min_length=43, max_length=512)


__all__ = [
    "AccessCredential", "IssuedWorkloadCredential", "WorkloadGrant",
    "canonical_grant_manifest_digest",
]
