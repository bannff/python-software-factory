"""Brick metadata indexing logic for Foreman."""

from pathlib import Path
from typing import Any
import yaml


def _validate_brick_metadata(metadata: dict[str, Any], brick_path: str) -> tuple[bool, str]:
    """Validate BRICK.yaml metadata structure.
    
    Args:
        metadata: Parsed YAML metadata dictionary
        brick_path: Path to the brick for error reporting
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    required_fields = ["name", "type", "namespace"]
    
    if not isinstance(metadata, dict):
        return False, f"Invalid metadata structure (not a dict) in {brick_path}"
    
    for field in required_fields:
        if field not in metadata:
            return False, f"Missing required field '{field}' in {brick_path}"
    
    if metadata.get("type") not in ["component", "base"]:
        return False, f"Invalid type '{metadata.get('type')}' in {brick_path}, must be 'component' or 'base'"
    if "mcp_gateway_host" in metadata and not isinstance(
        metadata["mcp_gateway_host"], bool,
    ):
        return False, f"mcp_gateway_host must be boolean in {brick_path}"
    return True, ""


def build_bricks_index(workspace_root: Path | None = None) -> dict[str, Any]:
    """Build BRICKS_INDEX from all BRICK.yaml files in workspace.
    
    Args:
        workspace_root: Root directory of the workspace. If None (default), uses current directory.
        
    Returns:
        Dictionary representing the complete BRICKS_INDEX with all brick metadata.
    """
    if workspace_root is None:
        workspace_root = Path.cwd()
    else:
        workspace_root = Path(workspace_root)
    
    index: dict[str, Any] = {
        "schema_version": 1,
        "workspace": str(workspace_root.name),
        "bricks": {
            "components": [],
            "bases": []
        },
        "missing_metadata": [],
        "invalid_metadata": []
    }
    
    # Scan components
    components_dir = workspace_root / "components"
    if components_dir.exists():
        for brick_dir in sorted(components_dir.iterdir()):
            if brick_dir.is_dir() and not brick_dir.name.startswith("."):
                brick_yaml = brick_dir / "BRICK.yaml"
                if brick_yaml.exists():
                    try:
                        with open(brick_yaml) as f:
                            metadata = yaml.safe_load(f)
                        
                        is_valid, error_msg = _validate_brick_metadata(
                            metadata, f"components/{brick_dir.name}"
                        )
                        
                        if is_valid:
                            index["bricks"]["components"].append(metadata)
                        else:
                            index["invalid_metadata"].append({
                                "path": f"components/{brick_dir.name}",
                                "error": error_msg
                            })
                    except (yaml.YAMLError, IOError, OSError) as e:
                        index["invalid_metadata"].append({
                            "path": f"components/{brick_dir.name}",
                            "error": f"Failed to read BRICK.yaml: {str(e)}"
                        })
                else:
                    index["missing_metadata"].append(f"components/{brick_dir.name}")
    
    # Scan bases
    bases_dir = workspace_root / "bases"
    if bases_dir.exists():
        for brick_dir in sorted(bases_dir.iterdir()):
            if brick_dir.is_dir() and not brick_dir.name.startswith("."):
                brick_yaml = brick_dir / "BRICK.yaml"
                if brick_yaml.exists():
                    try:
                        with open(brick_yaml) as f:
                            metadata = yaml.safe_load(f)
                        
                        is_valid, error_msg = _validate_brick_metadata(
                            metadata, f"bases/{brick_dir.name}"
                        )
                        
                        if is_valid:
                            index["bricks"]["bases"].append(metadata)
                        else:
                            index["invalid_metadata"].append({
                                "path": f"bases/{brick_dir.name}",
                                "error": error_msg
                            })
                    except (yaml.YAMLError, IOError, OSError) as e:
                        index["invalid_metadata"].append({
                            "path": f"bases/{brick_dir.name}",
                            "error": f"Failed to read BRICK.yaml: {str(e)}"
                        })
                else:
                    index["missing_metadata"].append(f"bases/{brick_dir.name}")
    
    return index


def write_bricks_index(
    index: dict[str, Any] | None = None,
    workspace_root: Path | None = None,
    output_path: Path | str | None = None
) -> dict[str, Any]:
    """Write BRICKS_INDEX.yaml to workspace root.
    
    Args:
        index: Pre-built index dictionary. If None, builds from scratch.
        workspace_root: Root directory of the workspace. If None (default), uses current directory.
        output_path: Path to write the index. If None (default), writes to BRICKS_INDEX.yaml in workspace root.
        
    Returns:
        Result dictionary with status and path information.
    """
    if workspace_root is None:
        workspace_root = Path.cwd()
    else:
        workspace_root = Path(workspace_root)
    
    if index is None:
        index = build_bricks_index(workspace_root)
    
    if output_path is None:
        output_path = workspace_root / "BRICKS_INDEX.yaml"
    else:
        output_path = Path(output_path)
    
    try:
        with open(output_path, "w") as f:
            yaml.dump(index, f, default_flow_style=False, sort_keys=False)
        
        return {
            "status": "success",
            "path": str(output_path),
            "components_count": len(index["bricks"]["components"]),
            "bases_count": len(index["bricks"]["bases"]),
            "missing_metadata_count": len(index["missing_metadata"]),
            "missing_metadata": index["missing_metadata"],
            "invalid_metadata_count": len(index.get("invalid_metadata", [])),
            "invalid_metadata": index.get("invalid_metadata", [])
        }
    except (IOError, OSError, yaml.YAMLError) as e:
        return {
            "status": "error",
            "error": f"Failed to write BRICKS_INDEX.yaml: {str(e)}",
            "path": str(output_path)
        }
