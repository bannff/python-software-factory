#!/usr/bin/env python3
"""Extract lazy singleton boilerplate from server.py files into make_lazy_runner.

Replaces the hand-rolled pattern:

    _mcp: FastMCP | None = None

    def get_mcp_server() -> FastMCP:
        global _mcp
        if _mcp is None:
            _mcp = create_mcp_server()
        return _mcp

    def main() -> None:
        get_mcp_server().run()

    if __name__ == "__main__":
        main()

With the shared utility:

    from factory.mcp_utils.server import make_lazy_runner

    get_mcp_server, main = make_lazy_runner(create_mcp_server)

    if __name__ == "__main__":
        main()
"""

from __future__ import annotations

import re
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent

# The boilerplate block to remove (regex handles minor whitespace variations)
BOILERPLATE_RE = re.compile(
    r"\n*# Module-level server for direct execution only\n"
    r"_mcp: FastMCP \| None = None\n"
    r"\n+"
    r"def get_mcp_server\(\) -> FastMCP:\n"
    r'    """Lazy singleton for direct execution \(not via aggregator\)\."""\n'
    r"    global _mcp\n"
    r"    if _mcp is None:\n"
    r"        _mcp = create_mcp_server\(\)\n"
    r"    return _mcp\n"
    r"\n+"
    r"def main\(\) -> None:\n"
    r'    """Run the MCP server\."""\n'
    r"    get_mcp_server\(\)\.run\(\)\n"
    r"\n+"
    r'if __name__ == "__main__":\n'
    r"    main\(\)\n*",
    re.MULTILINE,
)

REPLACEMENT = (
    "\n\nget_mcp_server, main = make_lazy_runner(create_mcp_server)\n"
    "\n"
    'if __name__ == "__main__":\n'
    "    main()\n"
)

IMPORT_LINE = "from factory.mcp_utils.server import make_lazy_runner"



def find_server_files() -> list[Path]:
    """Find all server.py files with the boilerplate pattern."""
    results = []
    for pattern in ["components/*/src/factory/*/server.py", "bases/*/src/factory/*/server.py"]:
        for path in WORKSPACE.glob(pattern):
            content = path.read_text()
            if "_mcp: FastMCP | None = None" in content and "def get_mcp_server" in content:
                results.append(path)
    return sorted(results)


def transform_file(path: Path, dry_run: bool = False) -> bool:
    """Transform a single server.py file."""
    content = path.read_text()

    # Check if already transformed
    if "make_lazy_runner" in content:
        print(f"  SKIP (already transformed): {path.relative_to(WORKSPACE)}")
        return False

    # Replace the boilerplate
    new_content = BOILERPLATE_RE.sub(REPLACEMENT, content)
    if new_content == content:
        print(f"  WARN (regex didn't match): {path.relative_to(WORKSPACE)}")
        return False

    # Add the import
    if IMPORT_LINE not in new_content:
        # Insert after the last existing import from factory.mcp_utils or fastmcp
        lines = new_content.split("\n")
        insert_idx = 0
        for i, line in enumerate(lines):
            if line.startswith(("from ", "import ")) and not line.startswith("from ."):
                # Skip relative imports, track last absolute import
                pass
            if line.startswith("from factory.mcp_utils") or line.startswith("from fastmcp"):
                insert_idx = i + 1
            elif line.startswith("from .") and insert_idx == 0:
                # First relative import — put our import before it
                insert_idx = i

        # If we didn't find a good spot, put after last top-level import
        if insert_idx == 0:
            for i, line in enumerate(lines):
                if line.startswith(("from ", "import ")):
                    insert_idx = i + 1

        lines.insert(insert_idx, IMPORT_LINE)
        new_content = "\n".join(lines)

    if dry_run:
        print(f"  DRY RUN: {path.relative_to(WORKSPACE)}")
        return True

    path.write_text(new_content)
    print(f"  FIXED: {path.relative_to(WORKSPACE)}")
    return True


def main():
    files = find_server_files()
    print(f"Found {len(files)} server.py files with boilerplate\n")

    fixed = 0
    for path in files:
        if transform_file(path):
            fixed += 1

    print(f"\nTransformed {fixed}/{len(files)} files")


if __name__ == "__main__":
    main()
