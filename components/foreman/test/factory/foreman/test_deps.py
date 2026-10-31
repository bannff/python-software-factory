"""Tests for brick dependency resolver."""

import tempfile
from pathlib import Path

from factory.foreman.brick_metadata import (
    read_brick_dependencies,
    read_brick_pip_packages,
)
from factory.foreman.deps import resolve_dependencies, _scan_brick_imports


def _workspace_root() -> Path:
    """Get the actual workspace root."""
    return Path(__file__).parents[5]


def test_resolve_single_brick():
    """Resolve deps for a brick with known imports."""
    result = resolve_dependencies(["mcp_utils"], _workspace_root())
    assert result["requested"] == ["mcp_utils"]
    assert "mcp_utils" in result["resolved"]
    assert result["not_found"] == []




def test_typed_mcp_bricks_declare_shared_transport() -> None:
    """Typed MCP bricks declare the shared native mcp v2 transport edge."""
    workspace = _workspace_root()
    for brick in ("test", "foreman"):
        assert "mcp_utils" in read_brick_dependencies(brick, workspace)
        packages = read_brick_pip_packages(brick, workspace) or []
        assert any(package.startswith("mcp[cli]==2.1.1") for package in packages)


def test_resolve_multiple_bricks():
    """Multiple requested bricks are all resolved."""
    result = resolve_dependencies(["cache", "graph"], _workspace_root())
    assert "cache" in result["resolved"]
    assert "graph" in result["resolved"]


def test_declared_dependency_resolves_without_python_import():
    """MCP-only BRICK.yaml edges participate in transitive resolution."""
    result = resolve_dependencies(["machine_learning"], _workspace_root())
    assert "dataset" in result["required"]
    assert "dataset" in result["resolved"]


def test_resolve_returns_python_packages():
    """Third-party imports are mapped to pip packages."""
    result = resolve_dependencies(["foreman"], _workspace_root())
    assert isinstance(result["python_packages"], list)
    # foreman uses yaml and the native mcp SDK at minimum
    pkg_names = " ".join(result["python_packages"])
    assert "pyyaml" in pkg_names
    assert "mcp[cli]==2.1.1" in pkg_names


def test_resolve_not_found():
    """Non-existent bricks are reported."""
    result = resolve_dependencies(["nonexistent_brick_xyz"], _workspace_root())
    assert "nonexistent_brick_xyz" in result["not_found"]
    assert "nonexistent_brick_xyz" not in result["resolved"]


def test_resolve_empty_list():
    """Empty input returns empty output."""
    result = resolve_dependencies([], _workspace_root())
    assert result["requested"] == []
    assert result["resolved"] == []
    assert result["required"] == []


def test_resolve_required_vs_requested():
    """Required bricks are those pulled in transitively, not requested."""
    result = resolve_dependencies(["foreman"], _workspace_root())
    # mcp_utils is required (transitive), not requested
    if "mcp_utils" in result["resolved"]:
        assert "mcp_utils" in result["required"]
        assert "mcp_utils" not in result["requested"]


def test_scan_brick_imports_returns_sets():
    """_scan_brick_imports returns factory bricks and third-party sets."""
    src = _workspace_root() / "components" / "foreman" / "src" / "factory" / "foreman"
    factory_bricks, third_party = _scan_brick_imports(src)
    assert isinstance(factory_bricks, set)
    assert isinstance(third_party, set)
    assert "mcp_utils" in factory_bricks
    assert "yaml" in third_party


def test_resolve_with_synthetic_workspace():
    """Test with a minimal synthetic workspace."""
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        # Create brick_a that imports brick_b
        for name, code in [
            ("brick_a", "from factory.brick_b.interface import something\nimport yaml\n"),
            ("brick_b", "import json\nimport pydantic\n"),
        ]:
            src = ws / "components" / name / "src" / "factory" / name
            src.mkdir(parents=True)
            (src / "__init__.py").write_text("")
            (src / "core.py").write_text(code)

        result = resolve_dependencies(["brick_a"], ws)
        assert "brick_a" in result["resolved"]
        assert "brick_b" in result["resolved"]
        assert "brick_b" in result["required"]
        assert "pyyaml" in " ".join(result["python_packages"])


def test_scan_adapter_imports_neo4j():
    """Adapter scanner finds lazy imports in neo4j adapter."""
    ws = _workspace_root()
    src = ws / "components" / "graph" / "src" / "factory" / "graph"
    from factory.foreman.deps import _scan_adapter_imports
    result = _scan_adapter_imports(src, ["neo4j"])
    assert "neo4j" in result


def test_scan_adapter_imports_otel_span():
    """Adapter scanner finds guarded imports in the otel_span adapter."""
    ws = _workspace_root()
    src = ws / "components" / "evals" / "src" / "factory" / "evals"
    from factory.foreman.deps import _scan_adapter_imports
    result = _scan_adapter_imports(src, ["otel_span"])
    assert "opentelemetry" in result


def test_resolve_with_include_adapters():
    """include_adapters pulls lazy adapter deps into python_packages."""
    result = resolve_dependencies(
        ["graph"], _workspace_root(), include_adapters=["neo4j"],
    )
    pkg_str = " ".join(result["python_packages"])
    assert "neo4j" in pkg_str
    assert "neo4j" in result["adapter_imports"]


def test_resolve_deep_scan_finds_lazy():
    """Deep scan (ast.walk) finds lazy adapter imports without include_adapters."""
    result = resolve_dependencies(["graph"], _workspace_root())
    pkg_str = " ".join(result["python_packages"])
    # Deep scan now catches imports inside functions/try-except
    assert "neo4j" in pkg_str
    assert "networkx" in pkg_str


def test_scan_adapter_imports_synthetic():
    """Adapter scanner works with synthetic adapter files."""
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        src = ws / "components" / "mybrick" / "src" / "factory" / "mybrick"
        adapters = src / "runtime" / "adapters"
        adapters.mkdir(parents=True)
        (adapters / "redis_adapter.py").write_text(
            "def connect():\n    import redis\n    return redis.Redis()\n"
        )
        from factory.foreman.deps import _scan_adapter_imports
        result = _scan_adapter_imports(src, ["redis"])
        assert "redis" in result
