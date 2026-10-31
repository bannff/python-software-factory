"""DTOs for authoring Events MCP tools."""
from __future__ import annotations

from .base import DTO, JsonObject


class ValidateSubscriptionsInput(DTO):
    dry_run: bool = True


class UpsertSubscriptionInput(DTO):
    subscription_id: str
    subscription_data: JsonObject
    dry_run: bool = False


class DeleteSubscriptionInput(DTO):
    subscription_id: str


class AuthoringStatusOutput(DTO):
    enabled: bool
    config_dir: str
    subscriptions_dir: str
    env_var: str


class ValidationOutput(DTO):
    ok: bool
    valid: int | None = None
    errors: list[JsonObject | str] = []
    error: str | None = None


class AuthoringMutationOutput(DTO):
    ok: bool
    dry_run: bool | None = None
    would_write: str | None = None
    path: str | None = None
    deleted: str | None = None
    details: list[JsonObject] | None = None
    error: str | None = None
