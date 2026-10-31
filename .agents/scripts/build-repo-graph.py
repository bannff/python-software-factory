#!/usr/bin/env python3
"""Build a structural index of this repo's own Python source.

Stdlib-only (ast + sqlite3), no third-party dependency. Walks
components/, bases/, projects/ and records files, classes/functions,
imports, and best-effort call edges into a local SQLite file at
.agents/.repo-graph/graph.sqlite (gitignored, regenerable any time).

This indexes THIS repo's factory source for agent development —
not the `graph` brick, which is a runtime capability for products
built ON this repo. Different layer entirely.

Usage:
    python .agents/scripts/build-repo-graph.py build
    python .agents/scripts/build-repo-graph.py find-symbol <name>
    python .agents/scripts/build-repo-graph.py find-importers <module>
    python .agents/scripts/build-repo-graph.py find-callers <function_name>
"""
from __future__ import annotations

import ast
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / ".agents" / ".repo-graph" / "graph.sqlite"
SCAN_DIRS = ("components", "bases", "projects")
SKIP_PARTS = {"__pycache__", ".venv", "node_modules", "dist", "build", ".git"}


def _iter_py_files():
    for top in SCAN_DIRS:
        base = ROOT / top
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            if SKIP_PARTS & set(path.parts):
                continue
            yield path


def _brick_for(path: Path) -> str:
    """Best-effort brick name: the dir right after components/bases/projects."""
    rel = path.relative_to(ROOT).parts
    return rel[1] if len(rel) > 1 else "?"


def _init_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        DROP TABLE IF EXISTS files;
        DROP TABLE IF EXISTS symbols;
        DROP TABLE IF EXISTS imports;
        DROP TABLE IF EXISTS calls;
        CREATE TABLE files (path TEXT PRIMARY KEY, brick TEXT);
        CREATE TABLE symbols (file TEXT, name TEXT, kind TEXT, lineno INTEGER);
        CREATE TABLE imports (file TEXT, module TEXT, name TEXT);
        CREATE TABLE calls (file TEXT, caller TEXT, callee TEXT, lineno INTEGER);
        CREATE INDEX idx_symbols_name ON symbols(name);
        CREATE INDEX idx_imports_module ON imports(module);
        CREATE INDEX idx_calls_callee ON calls(callee);
    """)


def _record_imports(conn, rel: str, tree: ast.Module) -> None:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                conn.execute("INSERT INTO imports VALUES (?,?,?)", (rel, alias.name, None))
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                conn.execute(
                    "INSERT INTO imports VALUES (?,?,?)", (rel, node.module, alias.name),
                )


def _record_symbols_and_calls(conn, rel: str, tree: ast.Module) -> None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            kind = "class" if isinstance(node, ast.ClassDef) else "function"
            conn.execute(
                "INSERT INTO symbols VALUES (?,?,?,?)", (rel, node.name, kind, node.lineno),
            )
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for inner in ast.walk(node):
                if isinstance(inner, ast.Call):
                    callee = _call_name(inner.func)
                    if callee:
                        conn.execute(
                            "INSERT INTO calls VALUES (?,?,?,?)",
                            (rel, node.name, callee, inner.lineno),
                        )


def _call_name(func_node: ast.expr) -> str | None:
    if isinstance(func_node, ast.Name):
        return func_node.id
    if isinstance(func_node, ast.Attribute):
        return func_node.attr
    return None


def build() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    _init_db(conn)
    scanned, failed = 0, 0
    for path in _iter_py_files():
        rel = str(path.relative_to(ROOT))
        conn.execute("INSERT INTO files VALUES (?,?)", (rel, _brick_for(path)))
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        except (SyntaxError, UnicodeDecodeError):
            failed += 1
            continue
        _record_imports(conn, rel, tree)
        _record_symbols_and_calls(conn, rel, tree)
        scanned += 1
    conn.commit()
    conn.close()
    print(f"Indexed {scanned} files ({failed} failed to parse) -> {DB_PATH}")


def find_symbol(name: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    for row in conn.execute(
        "SELECT file, kind, lineno FROM symbols WHERE name = ? ORDER BY file", (name,),
    ):
        print(f"{row[1]:>8}  {row[0]}:{row[2]}")


def find_importers(module: str) -> None:
    """Match module='X' / module LIKE 'X.%' (absolute imports), and
    ``from . import X`` / ``from .X import ...`` (relative imports, where
    ``module`` is the relative dot path and ``name`` is the imported name)."""
    conn = sqlite3.connect(DB_PATH)
    leaf = module.rsplit(".", 1)[-1]
    for row in conn.execute(
        """SELECT DISTINCT file FROM imports
           WHERE module = ? OR module LIKE ?
              OR name = ? OR module LIKE ?
           ORDER BY file""",
        (module, f"{module}.%", leaf, f"%{leaf}"),
    ):
        print(row[0])


def find_callers(func_name: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    for row in conn.execute(
        "SELECT DISTINCT file, caller FROM calls WHERE callee = ? ORDER BY file", (func_name,),
    ):
        print(f"{row[0]}  (in {row[1]})")


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "build":
        build()
    elif cmd == "find-symbol" and args:
        find_symbol(args[0])
    elif cmd == "find-importers" and args:
        find_importers(args[0])
    elif cmd == "find-callers" and args:
        find_callers(args[0])
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
