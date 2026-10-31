"""Path Traversal game adapter (OWASP A01).

Agent finds directory traversal vulnerabilities.
Validates that findings reference unsanitized file path input.
"""

from __future__ import annotations

from typing import Any

from .security_base import SecurityGameRules


class PathTraversalRules(SecurityGameRules):
    """Directory/path traversal vulnerability finding game."""

    game_type: str = "path_traversal"

    def _validate_finding(self, move: dict[str, Any]) -> bool:
        """Check for path traversal evidence."""
        evidence = move.get("evidence", "")
        return any(
            kw in evidence.lower()
            for kw in ("traversal", "path", "../", "directory", "file_path", "open(", "realpath")
        )
