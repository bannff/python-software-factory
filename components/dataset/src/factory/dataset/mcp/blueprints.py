"""Named MCP operations for validated, human-gated DatasetBlueprints."""
from __future__ import annotations

from pathlib import Path

from typing import Any

from factory.mcp_utils.interface import ToolResult, deterministic, operational

from .contracts.blueprints import (
    BlueprintMaterializationOutput, BlueprintValidationOutput,
    MaterializeBlueprintInput, ValidateBlueprintInput,
)


def register(mcp: Any, storage_root: Path) -> None:
    registered_root = storage_root

    @mcp.tool(name="dataset_validate_blueprint")
    @deterministic(input_model=ValidateBlueprintInput, output_model=BlueprintValidationOutput)
    def validate_blueprint(
        blueprint_json: str, storage_root: str | None = None,
    ) -> ToolResult[BlueprintValidationOutput]:
        """Validate a frozen blueprint and all registered references without writes."""
        from ..interface import dataset_validate_blueprint
        from ..runtime.blueprint_models import DatasetBlueprint
        root = Path(storage_root) if storage_root is not None else registered_root
        return dataset_validate_blueprint(
            DatasetBlueprint.model_validate_json(blueprint_json), root,
        ).model_dump(mode="json")

    @mcp.tool(name="dataset_materialize_blueprint")
    @operational(input_model=MaterializeBlueprintInput, output_model=BlueprintMaterializationOutput)
    def materialize_blueprint(
        blueprint_json: str,
        approval_id: str,
        approval_revision: str,
        approval_digest: str,
        storage_root: str | None = None,
    ) -> ToolResult[BlueprintMaterializationOutput]:
        """Submit an approved blueprint through the existing durable Dataset job path."""
        from ..interface import dataset_materialize_blueprint
        from ..runtime.blueprint_models import DatasetBlueprint, DatasetHumanApprovalRef
        root = Path(storage_root) if storage_root is not None else registered_root
        return dataset_materialize_blueprint(
            DatasetBlueprint.model_validate_json(blueprint_json),
            DatasetHumanApprovalRef(
                id=approval_id, revision=approval_revision, digest=approval_digest,
            ),
            root,
        ).model_dump(mode="json")
