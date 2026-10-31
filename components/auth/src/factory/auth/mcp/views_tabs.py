"""Tab and action builders for Auth dashboard.

Exports:
- auth_read_tabs(): read-only tabs component (tokens, capabilities, health)
- auth_actions(): list of write-operation action dicts for action_pane

Split from views.py to stay under 200 LOC per file.
"""

from __future__ import annotations

from typing import Any



# ── Read-only tabs (lazy-loaded data) ──────────────────────────────


def auth_read_tabs() -> dict[str, Any]:
    """Tabs component for read-only auth data."""
    return {
        "id": "auth-read-tabs",
        "type": "tabs",
        "props": {
            "tabs": [
                {"id": "tokens", "label": "Token Operations",
                 "lazy_tool": "auth_auth.get_capabilities"},
                {"id": "capabilities", "label": "Capabilities",
                 "lazy_tool": "auth_auth.describe_config_schema"},
                {"id": "health", "label": "Health & Config",
                 "lazy_tool": "auth_auth.health_check"},
            ],
        },
    }


# ── Write-operation actions for the action_pane ────────────────────


def auth_actions() -> list[dict[str, Any]]:
    """Return action definitions for the auth action pane."""
    return [
        _exchange_token(),
        _introspect_token(),
        _get_user_info(),
        _refresh_token(),
        _revoke_token(),
        _resolve_principal(),
    ]


def _exchange_token() -> dict[str, Any]:
    return {
        "id": "exchange-token", "label": "Exchange Token", "icon": "🔄",
        "tool": "auth_auth.exchange_token",
        "submit_label": "Exchange",
        "fields": [
            {"name": "subject_token", "label": "Subject Token",
             "type": "textarea", "placeholder": "Paste token to exchange…",
             "tooltip": "The token you want to exchange (RFC 8693)"},
            {"name": "subject_token_type", "label": "Subject Token Type",
             "type": "select", "tooltip": "URN type of the subject token",
             "options": [
                 {"value": "urn:ietf:params:oauth:token-type:access_token",
                  "label": "Access Token"},
                 {"value": "urn:ietf:params:oauth:token-type:refresh_token",
                  "label": "Refresh Token"},
                 {"value": "urn:ietf:params:oauth:token-type:id_token",
                  "label": "ID Token"},
             ]},
            {"name": "requested_token_type", "label": "Requested Type",
             "type": "select", "tooltip": "Desired output token type",
             "options": [
                 {"value": "", "label": "Default"},
                 {"value": "urn:ietf:params:oauth:token-type:access_token",
                  "label": "Access Token"},
                 {"value": "urn:ietf:params:oauth:token-type:refresh_token",
                  "label": "Refresh Token"},
             ]},
            {"name": "audience", "label": "Audience", "type": "text",
             "placeholder": "Optional target audience",
             "tooltip": "Target audience for the exchanged token"},
            {"name": "scope", "label": "Scope", "type": "text",
             "placeholder": "openid profile email",
             "tooltip": "Space-separated scopes to request"},
        ],
    }


def _introspect_token() -> dict[str, Any]:
    return {
        "id": "introspect-token", "label": "Introspect Token", "icon": "🔍",
        "tool": "auth_auth.introspect_token",
        "submit_label": "Introspect",
        "fields": [
            {"name": "token", "label": "Token", "type": "textarea",
             "placeholder": "Paste token to introspect…",
             "tooltip": "Check if a token is active and view its claims"},
        ],
    }


def _get_user_info() -> dict[str, Any]:
    return {
        "id": "get-user-info", "label": "Get User Info", "icon": "👤",
        "tool": "auth_auth.get_user_info",
        "submit_label": "Get Info",
        "fields": [
            {"name": "access_token", "label": "Access Token",
             "type": "textarea", "placeholder": "Paste access token…",
             "tooltip": "Retrieve user profile from the IdP userinfo endpoint"},
        ],
    }


def _refresh_token() -> dict[str, Any]:
    return {
        "id": "refresh-token", "label": "Refresh Token", "icon": "♻️",
        "tool": "auth_auth.refresh_token",
        "submit_label": "Refresh",
        "fields": [
            {"name": "refresh_token", "label": "Refresh Token",
             "type": "textarea", "placeholder": "Paste refresh token…",
             "tooltip": "Exchange a refresh token for a new access token"},
            {"name": "scope", "label": "Scope", "type": "text",
             "placeholder": "openid profile",
             "tooltip": "Optional scopes — leave empty to keep original"},
        ],
    }


def _revoke_token() -> dict[str, Any]:
    return {
        "id": "revoke-token", "label": "⚠ Revoke Token", "icon": "🗑️",
        "tool": "auth_auth.revoke_token",
        "submit_label": "Revoke",
        "fields": [
            {"name": "token", "label": "Token", "type": "textarea",
             "placeholder": "Paste token to revoke…",
             "tooltip": "Permanently invalidate this token at the IdP"},
            {"name": "token_type_hint", "label": "Token Type Hint",
             "type": "select", "tooltip": "Hint to help the IdP locate the token",
             "options": [
                 {"value": "", "label": "Auto-detect"},
                 {"value": "access_token", "label": "Access Token"},
                 {"value": "refresh_token", "label": "Refresh Token"},
             ]},
        ],
    }


def _resolve_principal() -> dict[str, Any]:
    return {
        "id": "resolve-principal", "label": "Resolve Principal", "icon": "🎯",
        "tool": "auth_auth.resolve_principal",
        "submit_label": "Resolve",
        "fields": [],
    }
