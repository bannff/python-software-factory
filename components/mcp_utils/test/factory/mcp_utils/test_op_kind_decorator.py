"""Tests for the ``op_kind`` trait decorator (bd:python-factory-rk4hc).

Contract A / Req 15.3: ``@op_kind(kind)`` is a sibling trait to
``deterministic`` / ``operational`` / ``authoring``. It sets ``_mcp_op_kind``
on the function (the closed value set ``{shell,read,write,authoring}``) and
rejects unknown kinds loudly at decoration time.
"""
from __future__ import annotations

import pytest

from factory.mcp_utils.interface import op_kind, OP_KINDS


def test_op_kind_sets_attr_for_each_allowed_kind() -> None:
    for kind in ("shell", "read", "write", "authoring"):
        @op_kind(kind)
        def tool() -> None:  # pragma: no cover - body never called
            ...

        assert getattr(tool, "_mcp_op_kind") == kind


def test_op_kind_returns_same_function() -> None:
    def tool() -> int:
        return 7

    decorated = op_kind("read")(tool)
    assert decorated is tool
    assert decorated() == 7


def test_op_kind_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError):
        op_kind("network")


def test_op_kind_closed_value_set() -> None:
    assert OP_KINDS == frozenset({"shell", "read", "write", "authoring"})


def test_op_kind_exported_from_package_root() -> None:
    import factory.mcp_utils as pkg

    assert "op_kind" in pkg.__all__
    assert pkg.op_kind is op_kind


def test_op_kind_composes_with_category_trait() -> None:
    from factory.mcp_utils.interface import deterministic

    @op_kind("read")
    @deterministic
    def tool() -> None:  # pragma: no cover - body never called
        ...

    # Orthogonal axes — both traits coexist on the same fn.
    assert getattr(tool, "_mcp_op_kind") == "read"
    assert getattr(tool, "_mcp_category") == "deterministic"


def test_native_composer_import_does_not_load_legacy_facade() -> None:
    """A clean interpreter can load the v2 seam without FastMCP imports."""
    import subprocess
    import sys

    probe = """
import importlib.abc
import sys
class BlockLegacy(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'fastmcp' or fullname.startswith('fastmcp.'):
            raise RuntimeError(f'legacy import attempted: {fullname}')
sys.meta_path.insert(0, BlockLegacy())
from factory.mcp_utils.runtime.native_v2_composer import NativeMCPV2Composer
assert 'factory.mcp_utils.interface' not in sys.modules
assert 'fastmcp' not in sys.modules
print(NativeMCPV2Composer.__name__)
"""
    completed = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, check=True, text=True,
    )
    assert completed.stdout.strip() == "NativeMCPV2Composer"
