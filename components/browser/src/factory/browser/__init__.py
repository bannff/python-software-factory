"""Browser automation component with pluggable protocol adapters."""

from .interface import Runtime, create_server

__all__ = ["Runtime", "create_server"]
