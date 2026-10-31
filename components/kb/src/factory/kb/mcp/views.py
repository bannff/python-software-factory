"""UIView definitions for KB brick — re-export shim.

The canonical views are registered via ``tools/views.py`` (loaded by
the MCP aggregator through ``tools/__init__.py``).  This module
re-exports the register function so that either import path works.
"""

from .tools.views import register  # noqa: F401

__all__ = ["register"]
