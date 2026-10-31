"""Caller-bound MCP adapter for protected artifact materialization."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from factory.mcp_utils.interface import ProtectedArtifactRef, get_service


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class _MaterializedData(_Strict):
    content: dict[str, Any]


class _ToolResult(_Strict):
    schema_version: Literal["v1"]
    ok: Literal[True]
    data: _MaterializedData
    error: None
    idempotency_key: str | None


class _NativeToolResult(_Strict):
    kind: Literal["tool"]
    structured_content: _ToolResult
    content: list[Any]
    meta: dict[str, Any]


class _NativeEnvelope(_Strict):
    ok: Literal[True]
    result: _NativeToolResult
    error: None = None
    idempotency_key: str | None = None


class MCPProtectedArtifactMaterializer:
    """Invoke Storage's hidden materializer with an exact artifact binding."""

    def _invoker(self) -> Any:
        factory = get_service("tool_invoker_for_caller")
        if not callable(factory):
            raise ValueError("protected artifact unavailable")
        invoker = factory("integrations")
        if not callable(invoker):
            raise ValueError("protected artifact unavailable")
        return invoker

    def materialize(
        self, artifact: ProtectedArtifactRef, principal_id: str, tenant_id: str,
    ) -> dict[str, Any]:
        artifact_data = artifact.model_dump(mode="json")
        binding = {
            "artifact_ref": artifact.artifact_ref,
            "fingerprint": artifact.fingerprint,
        }
        try:
            raw = self._invoker()(
                {
                    "brick_name": "storage",
                    "tool_name": "protected_artifact_materialize",
                },
                arguments={"artifact": artifact_data},
                protected_artifact=binding,
                idempotency_key=f"protected-artifact:{artifact.fingerprint}",
                envelope={
                    "principal_id": principal_id,
                    "tenant_id": tenant_id,
                },
            )
            result = _NativeEnvelope.model_validate(raw)
            return dict(result.result.structured_content.data.content)
        except Exception as exc:
            raise ValueError("protected artifact unavailable") from exc
