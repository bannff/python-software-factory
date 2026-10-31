"""Canary: the oracle ENGINE is domain-agnostic (bd python-factory-216ti).

Asserts ZERO ``if domain ==`` branches, ZERO ``"security"`` literal, and
ZERO ``import factory.security`` anywhere under the oracle runtime/ tree.
Domain selection MUST be registry-overlay + generic fallback only. This
guards the meta-frozen discipline against regression.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

_RUNTIME_DIR = (
    Path(__file__).resolve().parents[3]
    / "src" / "factory" / "oracle" / "runtime"
)


def _runtime_py_files() -> list[Path]:
    files = [
        p for p in _RUNTIME_DIR.rglob("*.py")
        if "__pycache__" not in str(p)
    ]
    assert files, f"no runtime files found under {_RUNTIME_DIR}"
    return files


class TestNoSecurityCoupling:
    """The oracle engine carries no domain literals or cross-imports."""

    def test_no_security_literal(self) -> None:
        for path in _runtime_py_files():
            assert "security" not in path.read_text().lower(), (
                f"'security' literal leaked into oracle engine: {path}"
            )

    def test_no_import_factory_security(self) -> None:
        pattern = re.compile(r"import\s+factory\.security|from\s+factory\.security")
        for path in _runtime_py_files():
            assert not pattern.search(path.read_text()), (
                f"factory.security import in oracle engine: {path}"
            )

    def test_no_if_domain_equals_branch(self) -> None:
        """No ``if domain == ...`` (or ``==`` against a domain literal)."""
        text_pattern = re.compile(r"if\s+domain\s*==")
        for path in _runtime_py_files():
            source = path.read_text()
            assert not text_pattern.search(source), (
                f"hardcoded 'if domain ==' branch in oracle engine: {path}"
            )
            # AST-level: no Compare whose operand is a Name 'domain' with Eq.
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Compare) and any(
                    isinstance(op, (ast.Eq, ast.NotEq)) for op in node.ops
                ):
                    names = {
                        n.id for n in ast.walk(node)
                        if isinstance(n, ast.Name)
                    }
                    assert "domain" not in names, (
                        f"AST domain-equality branch in oracle engine: {path}"
                    )

    def test_no_cross_brick_imports(self) -> None:
        """Only mcp_utils is imported cross-brick; never another brick's internals."""
        for path in _runtime_py_files():
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                mod = None
                if isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                elif isinstance(node, ast.Import):
                    mod = node.names[0].name
                if mod and mod.startswith("factory.") and not mod.startswith(
                    ("factory.oracle", "factory.mcp_utils")
                ):
                    raise AssertionError(
                        f"cross-brick import {mod!r} in oracle engine: {path}"
                    )
