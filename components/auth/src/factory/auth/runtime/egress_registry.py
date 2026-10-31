"""Immutable provider/route registry — the only source of egress authority.

Routes are data, not caller input. Each route fixes the HTTPS origin, method,
path template, required scopes, the allowed payload fields, and which durable
secret slot kind backs it. This foundation ships two FAKE-backed provider
families (Microsoft delegated, Adobe client-credentials); real provider network
calls belong to child stories.
"""
from __future__ import annotations

from .egress_models import ProviderRoute

_ROUTES: dict[tuple[str, str], ProviderRoute] = {}


def register_route(route: ProviderRoute) -> None:
    """Register one immutable route; a differing duplicate is rejected."""
    key = (route.provider_id, route.route_id)
    existing = _ROUTES.get(key)
    if existing is not None and existing != route:
        raise ValueError("provider route is already registered with different authority")
    _ROUTES[key] = route


def resolve_route(provider_id: str, route_id: str) -> ProviderRoute | None:
    """Resolve one route, or None when unknown."""
    return _ROUTES.get((provider_id, route_id))


def _seed_defaults() -> None:
    register_route(ProviderRoute(
        provider_id="microsoft", route_id="send_mail",
        origin="https://graph.microsoft.com", method="POST",
        path_template="/v1.0/me/sendMail",
        required_scopes=("Mail.Send",),
        allowed_fields=frozenset({"subject", "body", "to"}),
        request_schema=(("subject", "str"), ("body", "str"), ("to", "str")),
        secret_slot_kind="refresh_token",
    ))
    register_route(ProviderRoute(
        provider_id="microsoft", route_id="list_messages",
        origin="https://graph.microsoft.com", method="GET",
        path_template="/v1.0/me/messages",
        required_scopes=("Mail.Read",),
        allowed_fields=frozenset({"top", "filter"}),
        request_schema=(("top", "int"), ("filter", "str")),
        secret_slot_kind="refresh_token",
    ))
    register_route(ProviderRoute(
        provider_id="adobe", route_id="indesign_datamerge",
        origin="https://indesign.adobe.io", method="POST",
        path_template="/v3/merge-data",
        required_scopes=("openid", "AdobeID"),
        allowed_fields=frozenset({"template_ref", "data_ref"}),
        request_schema=(("template_ref", "str"), ("data_ref", "str")),
        secret_slot_kind="client_secret",
    ))


_seed_defaults()


__all__ = ["register_route", "resolve_route"]
