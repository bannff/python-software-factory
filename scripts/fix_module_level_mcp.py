#!/usr/bin/env python3
"""Fix module-level mcp = create_mcp_server() across all bricks.

Fixes #250: Replace eager module-level server creation with lazy singleton.
This is a mechanical transformation applied uniformly.
"""

import re
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent


def fix_server_py(path: Path) -> bool:
    """Replace module-level mcp = create_mcp_server() with lazy get_mcp_server()."""
    text = path.read_text()
    if "mcp = create_mcp_server()" not in text:
        return False

    # Check if already has FastMCP type hint import
    has_fastmcp_import = "from fastmcp import FastMCP" in text or "FastMCP" in text

    # Pattern 1: with comment above
    text = re.sub(
        r'# (?:Module-level server for direct execution|Legacy compatibility.*)\n'
        r'mcp = create_mcp_server\(\)\n',
        '# Module-level server for direct execution only\n'
        '_mcp: FastMCP | None = None\n'
        '\n\n'
        'def get_mcp_server() -> FastMCP:\n'
        '    """Lazy singleton for direct execution (not via aggregator)."""\n'
        '    global _mcp\n'
        '    if _mcp is None:\n'
        '        _mcp = create_mcp_server()\n'
        '    return _mcp\n',
        text,
    )

    # Pattern 2: bare (no comment)
    text = re.sub(
        r'\nmcp = create_mcp_server\(\)\n',
        '\n# Module-level server for direct execution only\n'
        '_mcp: FastMCP | None = None\n'
        '\n\n'
        'def get_mcp_server() -> FastMCP:\n'
        '    """Lazy singleton for direct execution (not via aggregator)."""\n'
        '    global _mcp\n'
        '    if _mcp is None:\n'
        '        _mcp = create_mcp_server()\n'
        '    return _mcp\n',
        text,
    )

    # Fix main() to use get_mcp_server()
    text = text.replace('mcp.run()', 'get_mcp_server().run()')

    path.write_text(text)
    return True


def fix_interface_py(path: Path) -> bool:
    """Replace 'from .server import mcp as server' with create_mcp_server as create_server."""
    text = path.read_text()
    if "from .server import mcp as server" not in text and \
       "from .server import mcp as McpInstance" not in text:
        return False

    # Standard pattern
    text = text.replace(
        "from .server import mcp as server",
        "from .server import create_mcp_server as create_server",
    )
    text = text.replace('"server"', '"create_server"')
    text = text.replace("'server'", "'create_server'")

    # Foreman special case
    text = text.replace(
        "from .server import mcp as McpInstance",
        "from .server import get_mcp_server",
    )
    text = text.replace('"McpInstance"', '"get_mcp_server"')
    text = text.replace("'McpInstance'", "'get_mcp_server'")

    path.write_text(text)
    return True


def fix_test_py(path: Path) -> bool:
    """Replace 'from factory.X.server import mcp' with get_mcp_server pattern."""
    text = path.read_text()

    # Match: from factory.X.server import mcp
    m = re.search(r'from (factory\.\w+\.server) import mcp\b', text)
    if not m:
        return False

    module = m.group(1)

    # Replace import
    text = text.replace(
        f"from {module} import mcp",
        f"from {module} import get_mcp_server",
    )

    # If there's a helper like _get_tool that uses mcp directly, fix it
    # Pattern: tools = {t.name: t for t in mcp._tool_manager._tools.values()}
    text = text.replace(
        "tools = {t.name: t for t in mcp._tool_manager._tools.values()}",
        "mcp = get_mcp_server()\n    tools = {t.name: t for t in mcp._tool_manager._tools.values()}",
    )

    # For tests that use mcp directly (not via helper)
    # Add mcp = get_mcp_server() at the start of functions that reference mcp
    # But only if there's no _get_tool helper (those are handled above)
    if "_get_tool" not in text and "mcp" in text:
        # Replace bare mcp references with get_mcp_server()
        text = re.sub(r'\bmcp\._tool_manager', 'get_mcp_server()._tool_manager', text)
        text = re.sub(r'\bmcp\.name', 'get_mcp_server().name', text)
        # assert mcp is not None → assert get_mcp_server() is not None
        text = text.replace("assert mcp is not None", "assert get_mcp_server() is not None")

    path.write_text(text)
    return True


def main():
    # Fix server.py files
    server_files = list(WORKSPACE.glob("components/*/src/factory/*/server.py")) + \
                   list(WORKSPACE.glob("bases/*/src/factory/*/server.py"))
    
    fixed_servers = 0
    for f in sorted(server_files):
        if fix_server_py(f):
            print(f"  Fixed server: {f.relative_to(WORKSPACE)}")
            fixed_servers += 1

    # Fix interface.py files
    interface_files = list(WORKSPACE.glob("components/*/src/factory/*/interface.py")) + \
                      list(WORKSPACE.glob("bases/*/src/factory/*/interface.py"))
    
    fixed_interfaces = 0
    for f in sorted(interface_files):
        if fix_interface_py(f):
            print(f"  Fixed interface: {f.relative_to(WORKSPACE)}")
            fixed_interfaces += 1

    # Fix test files
    test_files = list(WORKSPACE.glob("components/*/test/factory/*/test_*.py")) + \
                 list(WORKSPACE.glob("bases/*/test/factory/*/test_*.py"))
    
    fixed_tests = 0
    for f in sorted(test_files):
        if fix_test_py(f):
            print(f"  Fixed test: {f.relative_to(WORKSPACE)}")
            fixed_tests += 1

    print(f"\nDone: {fixed_servers} servers, {fixed_interfaces} interfaces, {fixed_tests} tests")


if __name__ == "__main__":
    main()
