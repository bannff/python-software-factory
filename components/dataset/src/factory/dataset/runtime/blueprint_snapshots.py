"""Deterministic snapshot specifications derived from a frozen blueprint."""
from __future__ import annotations

from pathlib import Path

from .blueprint_codec import canonical_json
from .blueprint_models import DatasetBlueprint, DatasetBlueprintBinding
from .contracts import DatasetSnapshotRef, DatasetToolSchemaSnapshotRef
from .helpers import _sha256

SnapshotSpec = tuple[DatasetSnapshotRef, Path, bytes]
ToolSnapshotSpec = tuple[DatasetToolSchemaSnapshotRef, Path, bytes]


def blueprint_snapshot_specs(
    storage_root: Path,
    blueprint: DatasetBlueprint,
    binding: DatasetBlueprintBinding,
) -> tuple[SnapshotSpec, ToolSnapshotSpec]:
    """Return exact refs, paths, and bytes without writing any state."""
    snapshot_dir = storage_root.resolve() / "blueprints" / "snapshots"
    context_content = canonical_json({
        "blueprint_binding": binding.model_dump(mode="json"),
    })
    tool_content = canonical_json({
        "capabilities": [
            item.model_dump(mode="json") for item in blueprint.capabilities
        ],
        "allowed_tools": [],
    })
    context_digest = _sha256(context_content)
    tool_digest = _sha256(tool_content)
    context_path = snapshot_dir / f"context-{context_digest}.json"
    tool_path = snapshot_dir / f"tools-{tool_digest}.json"
    context = DatasetSnapshotRef(
        uri=context_path.resolve().as_uri(), digest=context_digest,
    )
    tools = DatasetToolSchemaSnapshotRef(
        uri=tool_path.resolve().as_uri(), digest=tool_digest, allowed_tools=[],
    )
    return (context, context_path, context_content), (tools, tool_path, tool_content)
