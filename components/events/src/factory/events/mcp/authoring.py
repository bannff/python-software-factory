"""Typed authoring MCP tools for Events."""
from __future__ import annotations

from typing import Callable, TYPE_CHECKING

from typing import Any
from factory.mcp_utils.interface import ToolResult, authoring, make_serializable

from .contracts.authoring import (
    AuthoringMutationOutput, AuthoringStatusOutput, DeleteSubscriptionInput,
    UpsertSubscriptionInput, ValidateSubscriptionsInput, ValidationOutput,
)
from .contracts.base import EmptyInput

if TYPE_CHECKING:
    from ..authoring import EventsAuthoring


def register(
    mcp: Any, get_authoring: Callable[[], "EventsAuthoring"],
    get_runtime: Callable[[], Any],
) -> None:
    """Register authoring tools with strict public contracts."""

    @mcp.tool()
    @authoring(input_model=EmptyInput, output_model=AuthoringStatusOutput)
    def events_authoring_get_status() -> ToolResult[AuthoringStatusOutput]:
        return make_serializable(get_authoring().get_status())

    @mcp.tool()
    @authoring(input_model=ValidateSubscriptionsInput, output_model=ValidationOutput)
    def events_authoring_validate_subscriptions(dry_run: bool = True) -> ToolResult[ValidationOutput]:
        return make_serializable(get_authoring().validate_subscriptions(dry_run=dry_run))

    @mcp.tool()
    @authoring(input_model=UpsertSubscriptionInput, output_model=AuthoringMutationOutput)
    def events_authoring_upsert_subscription(subscription_id: str,
        subscription_data: dict[str, object], dry_run: bool = False) -> ToolResult[AuthoringMutationOutput]:
        result = get_authoring().upsert_subscription(
            subscription_id, subscription_data, dry_run=dry_run,
        )
        if result.get("ok") and not dry_run:
            from ..runtime.subscriptions import SubscriptionDefinition
            get_runtime().get_subscription_registry().register(
                SubscriptionDefinition.model_validate(subscription_data),
            )
        return make_serializable(result)

    @mcp.tool()
    @authoring(input_model=DeleteSubscriptionInput, output_model=AuthoringMutationOutput)
    def events_authoring_delete_subscription(subscription_id: str) -> ToolResult[AuthoringMutationOutput]:
        result = get_authoring().delete_subscription(subscription_id)
        if result.get("ok"):
            get_runtime().get_subscription_registry().unregister(subscription_id)
        return make_serializable(result)
