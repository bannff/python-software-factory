"""Cedar policy evaluation adapter.

Provides Cedar policy language support alongside YAML policies.
Uses cedarpy for local evaluation or AWS Verified Permissions for managed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

Decision = Literal["allow", "deny"]


@dataclass
class CedarPolicy:
    """A Cedar policy loaded from file."""

    id: str
    content: str
    source_file: str


@dataclass
class CedarSchema:
    """A Cedar schema loaded from file."""

    content: str
    source_file: str


@dataclass
class CedarEvalRequest:
    """Request for Cedar policy evaluation."""

    principal: str  # e.g., "User::\"alice\""
    action: str  # e.g., "Action::\"read\""
    resource: str  # e.g., "Document::\"doc123\""
    context: dict[str, Any] | None = None


@dataclass
class CedarEvalResult:
    """Result of Cedar policy evaluation."""

    decision: Decision
    diagnostics: list[str]
    determining_policies: list[str]


class CedarAdapter:
    """Adapter for Cedar policy evaluation.

    Supports loading .cedar policy files and .cedarschema schema files.
    Can use local cedarpy or AWS Verified Permissions as backend.
    """

    def __init__(self, policies_dir: Path | None = None) -> None:
        self._policies: list[CedarPolicy] = []
        self._schema: CedarSchema | None = None
        self._backend: Literal["local", "avp"] = "local"

        if policies_dir:
            self._load_from_directory(policies_dir)

    def load_policy(self, policy_id: str, content: str, source: str = "") -> None:
        """Load a Cedar policy from string content."""
        self._policies.append(CedarPolicy(id=policy_id, content=content, source_file=source))

    def load_schema(self, content: str, source: str = "") -> None:
        """Load a Cedar schema from string content."""
        self._schema = CedarSchema(content=content, source_file=source)

    def evaluate(self, request: CedarEvalRequest) -> CedarEvalResult:
        """Evaluate a request against loaded Cedar policies.

        Falls back to deny if cedarpy is not available.
        """
        try:
            return self._evaluate_local(request)
        except ImportError:
            return CedarEvalResult(
                decision="deny",
                diagnostics=["cedarpy not installed - install with: pip install cedarpy"],
                determining_policies=[],
            )

    def validate_policies(self) -> list[str]:
        """Validate loaded policies against schema. Returns list of errors."""
        errors: list[str] = []
        try:
            import cedarpy

            policy_set = "\n".join(p.content for p in self._policies)
            schema = self._schema.content if self._schema else None

            # cedarpy.validate returns validation errors
            if schema:
                result = cedarpy.validate(policy_set, schema)
                if result.errors:
                    errors.extend(str(e) for e in result.errors)
        except ImportError:
            errors.append("cedarpy not installed")
        except Exception as e:
            errors.append(f"Validation error: {e}")

        return errors

    def get_policies(self) -> list[dict[str, Any]]:
        """Get list of loaded policies."""
        return [
            {"id": p.id, "source_file": p.source_file, "content_preview": p.content[:100]}
            for p in self._policies
        ]

    def health_check(self) -> dict[str, Any]:
        """Check Cedar adapter health."""
        try:
            import cedarpy

            return {
                "healthy": True,
                "backend": self._backend,
                "policy_count": len(self._policies),
                "has_schema": self._schema is not None,
                "cedarpy_available": True,
            }
        except ImportError:
            return {
                "healthy": False,
                "backend": self._backend,
                "policy_count": len(self._policies),
                "has_schema": self._schema is not None,
                "cedarpy_available": False,
                "error": "cedarpy not installed",
            }

    def _load_from_directory(self, policies_dir: Path) -> None:
        """Load all .cedar and .cedarschema files from directory."""
        if not policies_dir.exists():
            return

        # Load policies
        for path in policies_dir.glob("*.cedar"):
            content = path.read_text()
            self.load_policy(policy_id=path.stem, content=content, source=str(path))

        # Load schema (use first found)
        for path in policies_dir.glob("*.cedarschema"):
            content = path.read_text()
            self.load_schema(content=content, source=str(path))
            break

    def _evaluate_local(self, request: CedarEvalRequest) -> CedarEvalResult:
        """Evaluate using local cedarpy."""
        import cedarpy

        policy_set = "\n".join(p.content for p in self._policies)
        schema = self._schema.content if self._schema else None

        # Build entities (empty for now, can be extended)
        entities: list[dict[str, Any]] = []

        result = cedarpy.is_authorized(
            principal=request.principal,
            action=request.action,
            resource=request.resource,
            context=request.context or {},
            policies=policy_set,
            entities=json.dumps(entities),
            schema=schema,
        )

        return CedarEvalResult(
            decision="allow" if result.is_allowed else "deny",
            diagnostics=[str(d) for d in (result.diagnostics or [])],
            determining_policies=[str(p) for p in (result.determining_policies or [])],
        )
