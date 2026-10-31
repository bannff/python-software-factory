"""Base protocol for authentication backends.

Re-exports the AuthBackend Protocol from ports.py for adapter implementations.
"""
from __future__ import annotations

from factory.auth.runtime.ports import AuthBackend

__all__ = ["AuthBackend"]
