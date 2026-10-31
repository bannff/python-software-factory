"""Strict DTOs for authoring Security MCP tools."""
from __future__ import annotations
from typing import Any
from .base import DTO, EmptyInput

class AuthoringStatusOutput(DTO):
    enabled: bool; message: str | None = None; details: dict[str, Any] = {}
class RulesOutput(DTO):
    rules: list[dict[str, Any]]; count: int = 0
class RuleInput(DTO):
    id: str
class UpsertRuleInput(RuleInput):
    config: dict[str, Any]; dry_run: bool = False
class RuleOutput(DTO):
    success: bool; error: str | None = None; details: dict[str, Any] = {}
class TaxonomySeedOutput(DTO):
    success: bool; error: str | None = None; details: dict[str, Any] = {}
