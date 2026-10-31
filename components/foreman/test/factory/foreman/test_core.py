from factory.foreman import core
from pathlib import Path
import tempfile
import yaml


def test_sample():
    assert core is not None


def test_build_bricks_index():
    """Test building BRICKS_INDEX from actual workspace."""
    workspace_root = Path(__file__).parents[5]  # Navigate to repo root
    index = core.build_bricks_index(workspace_root)
    
    assert index["schema_version"] == 1
    assert "bricks" in index
    assert "components" in index["bricks"]
    assert "bases" in index["bricks"]
    assert "missing_metadata" in index
    assert "invalid_metadata" in index
    assert len(index["bricks"]["components"]) > 0
    assert len(index["bricks"]["bases"]) > 0


def test_write_bricks_index():
    """Test writing BRICKS_INDEX to a temporary location."""
    workspace_root = Path(__file__).parents[5]  # Navigate to repo root
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp:
        tmp_path = Path(tmp.name)
    
    try:
        result = core.write_bricks_index(workspace_root=workspace_root, output_path=tmp_path)
        
        assert result["status"] == "success"
        assert result["components_count"] >= 16
        assert result["bases_count"] >= 3
        assert result["missing_metadata_count"] == 0
        assert result["missing_metadata"] == []
        assert result["invalid_metadata_count"] == 0
        
        # Verify the file was written correctly
        with open(tmp_path) as f:
            written_index = yaml.safe_load(f)
        
        assert written_index["schema_version"] == 1
        assert len(written_index["missing_metadata"]) == 0
        assert len(written_index["invalid_metadata"]) == 0
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def test_validate_brick_metadata():
    """Test BRICK metadata validation."""
    # Valid metadata
    valid_metadata = {
        "name": "test",
        "type": "component",
        "namespace": "factory.test"
    }
    is_valid, error = core._validate_brick_metadata(valid_metadata, "test/path")
    assert is_valid is True
    assert error == ""
    
    # Missing required field
    invalid_metadata = {
        "name": "test",
        "namespace": "factory.test"
    }
    is_valid, error = core._validate_brick_metadata(invalid_metadata, "test/path")
    assert is_valid is False
    assert "Missing required field 'type'" in error
    
    # Invalid type
    invalid_type = {
        "name": "test",
        "type": "invalid",
        "namespace": "factory.test"
    }
    is_valid, error = core._validate_brick_metadata(invalid_type, "test/path")
    assert is_valid is False
    assert "Invalid type" in error
    
    # Not a dict
    is_valid, error = core._validate_brick_metadata([], "test/path")
    assert is_valid is False
    assert "not a dict" in error


def test_error_handling_malformed_yaml():
    """Test handling of malformed BRICK.yaml files."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        workspace = Path(tmp_dir)
        components_dir = workspace / "components"
        components_dir.mkdir()
        
        # Create a component with malformed YAML
        bad_component = components_dir / "bad_component"
        bad_component.mkdir()
        brick_yaml = bad_component / "BRICK.yaml"
        brick_yaml.write_text("invalid: yaml: content: [[[")
        
        index = core.build_bricks_index(workspace)
        
        assert len(index["invalid_metadata"]) == 1
        assert index["invalid_metadata"][0]["path"] == "components/bad_component"
        assert "Failed to read BRICK.yaml" in index["invalid_metadata"][0]["error"]


def test_error_handling_invalid_structure():
    """Test handling of BRICK.yaml files with invalid structure."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        workspace = Path(tmp_dir)
        components_dir = workspace / "components"
        components_dir.mkdir()
        
        # Create a component with missing required fields
        incomplete = components_dir / "incomplete"
        incomplete.mkdir()
        brick_yaml = incomplete / "BRICK.yaml"
        brick_yaml.write_text("name: incomplete\n")
        
        index = core.build_bricks_index(workspace)
        
        assert len(index["invalid_metadata"]) == 1
        assert index["invalid_metadata"][0]["path"] == "components/incomplete"
        assert "Missing required field" in index["invalid_metadata"][0]["error"]



def test_validate_gateway_host_metadata():
    valid = {"name": "host", "type": "base", "namespace": "factory.host",
             "mcp_gateway_host": True}
    assert core._validate_brick_metadata(valid, "test/path") == (True, "")

    invalid = {**valid, "mcp_gateway_host": "true"}
    is_valid, error = core._validate_brick_metadata(invalid, "test/path")
    assert is_valid is False
    assert "mcp_gateway_host must be boolean" in error
