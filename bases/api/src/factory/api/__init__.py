"""API base - HTTP entry point with REST/GraphQL adapters."""

from .interface import create_app, APIRuntime

__all__ = ["create_app", "APIRuntime"]
