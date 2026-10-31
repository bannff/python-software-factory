#!/usr/bin/env python3
"""Stdio-to-HTTP MCP proxy with Cognito M2M token auto-refresh.

Kiro launches this as a stdio MCP server. It fetches a Bearer token
from the Cognito OAuth2 endpoint, then proxies every JSON-RPC message
to the AgentCore MCP Gateway over HTTP. Tokens are refreshed
automatically when they expire.

Env vars (required):
    GATEWAY_URL          – MCP Gateway streamable-HTTP endpoint
    COGNITO_TOKEN_URL    – Cognito /oauth2/token endpoint
    COGNITO_CLIENT_ID    – App client ID (inbound pool)
    COGNITO_CLIENT_SECRET– App client secret
    COGNITO_SCOPE        – OAuth2 scope (e.g. art-mcp-gateway/invoke)
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
import urllib.parse

# ── config ──────────────────────────────────────────────────────────
GATEWAY_URL = os.environ["GATEWAY_URL"]
TOKEN_URL = os.environ["COGNITO_TOKEN_URL"]
CLIENT_ID = os.environ["COGNITO_CLIENT_ID"]
CLIENT_SECRET = os.environ["COGNITO_CLIENT_SECRET"]
SCOPE = os.environ.get("COGNITO_SCOPE", "")

# ── token cache ─────────────────────────────────────────────────────
_token: str = ""
_token_expires_at: float = 0.0


def _refresh_token() -> str:
    """Fetch a fresh M2M token from Cognito OAuth2 endpoint."""
    global _token, _token_expires_at
    body = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": SCOPE,
    }).encode()
    req = urllib.request.Request(
        TOKEN_URL,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
    _token = data["access_token"]
    # Refresh 60s before actual expiry
    _token_expires_at = time.time() + data.get("expires_in", 3600) - 60
    return _token


def get_token() -> str:
    if time.time() >= _token_expires_at:
        return _refresh_token()
    return _token


# ── proxy loop ──────────────────────────────────────────────────────

def proxy_request(line: str) -> str:
    """Send a JSON-RPC line to the gateway and return the response."""
    token = get_token()
    body = line.encode("utf-8")
    req = urllib.request.Request(
        GATEWAY_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def main() -> None:
    # Pre-fetch token so failures surface immediately
    get_token()
    sys.stderr.write(f"[agentcore-mcp-proxy] connected to {GATEWAY_URL}\n")
    sys.stderr.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            result = proxy_request(line)
            sys.stdout.write(result)
            if not result.endswith("\n"):
                sys.stdout.write("\n")
            sys.stdout.flush()
        except Exception as exc:
            # Return JSON-RPC error so the client doesn't hang
            try:
                req_id = json.loads(line).get("id")
            except Exception:
                req_id = None
            err = json.dumps({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32000, "message": str(exc)},
            })
            sys.stdout.write(err + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
