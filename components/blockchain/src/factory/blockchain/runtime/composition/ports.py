"""Neutral composition lifecycle ports; no economy semantics belong here."""
from __future__ import annotations

from typing import Mapping, Protocol


class ProfileRuntime(Protocol):
    """A mounted profile's neutral lifecycle facts."""

    def capabilities(self) -> Mapping[str, object]: ...

    def health_check(self) -> Mapping[str, object]: ...


class ProfileRuntimeFactory(Protocol):
    """Creates one profile runtime from trusted startup configuration."""

    def create(self, *, backend_id: str) -> ProfileRuntime: ...
