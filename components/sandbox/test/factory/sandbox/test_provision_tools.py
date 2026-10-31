"""Tests for sandbox.validate_manifest MCP tool logic."""
from __future__ import annotations

from factory.sandbox.runtime.manifest import SandboxManifest


def test_manifest_validates_minimal():
    """A minimal manifest with app_name + data_stores is valid."""
    m = SandboxManifest(
        app_name="TestApp",
        data_stores=[{"type": "dynamodb", "name": "t1"}],
    )
    assert m.app_name == "TestApp"
    assert len(m.data_stores) == 1


def test_manifest_validates_full():
    """A full manifest with all fields parses correctly."""
    m = SandboxManifest(
        app_name="FullApp",
        run_id="run-123",
        compute=[{"type": "lambda", "name": "fn1", "runtime": "python3.12"}],
        data_stores=[
            {"type": "dynamodb", "name": "t1"},
            {"type": "s3", "name": "b1"},
        ],
        auth={"strategy": "bypass"},
        service_deps=[{"type": "rpc", "name": "svc1"}],
        init_scripts=["echo init"],
    )
    assert len(m.compute) == 1
    assert len(m.data_stores) == 2
    assert m.auth.strategy == "bypass"


def test_manifest_defaults():
    """Empty optional fields get sensible defaults."""
    m = SandboxManifest(app_name="Defaults")
    assert m.compute == []
    assert m.data_stores == []
    assert m.auth.strategy == "bypass"
    assert m.cfn_template is None
    assert m.init_scripts == []
