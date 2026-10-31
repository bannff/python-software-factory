"""Strict Pydantic v2 contracts for Blueprint authoring MCP tools."""
from __future__ import annotations

from .contracts_base import JsonOutput, StrictInput


class UpdateServiceUrlInput(StrictInput):
    service_name: str
    url: str


class UpdateServiceUrlOutput(JsonOutput):
    updated: bool
    service: str
    url: str


__all__ = ["UpdateServiceUrlInput", "UpdateServiceUrlOutput"]
