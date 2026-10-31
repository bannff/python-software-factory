"""MCP resources for the domain brick."""
from __future__ import annotations

import json
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..runtime.runtime import DomainRuntime


def register(mcp: Any, runtime: "DomainRuntime") -> None:
    """Register MCP resources for the domain brick."""

    @mcp.resource("domain://manifests/{domain_id}")
    def get_manifest_resource(domain_id: str) -> str:
        """Live presentation manifest for a domain (generic on miss)."""
        manifest = runtime.get_manifest(domain_id)
        return json.dumps(manifest.model_dump(mode="json"), indent=2)
