"""SSRF-pinned HTTP egress transport for real provider adapters.

The broker injects a broker-held access token into ONE route call. This
transport enforces the route manifest as the sole authority:
- the request URL is built from the immutable route origin + path template
  (the caller supplies neither URL nor method nor headers);
- redirects are refused (``follow_redirects=False`` + explicit 3xx -> denied),
  closing the classic token-exfiltration-via-redirect SSRF;
- the response body is capped at ``route.max_bytes`` and the timeout at
  ``route.timeout_s``; and
- any secret/token-named field a provider might echo is redacted from the
  result before it can reach a caller.

The ``httpx.Client`` is injected so this is fully offline-testable with a
``MockTransport``. Token acquisition (client-credentials / refresh flows) for
real providers is a separate child story; this covers only the egress call.
"""
from __future__ import annotations

from typing import Any, Mapping

from ..egress_models import ProviderRoute, redact_secrets


class HttpProviderEgress:
    """Origin-pinned, redirect-refusing egress `call` over an injected client."""

    def __init__(self, client: Any) -> None:
        self._client = client  # httpx.Client (or a MockTransport-backed client)

    def call(self, route: ProviderRoute, access_token: str,
             payload: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
        if not route.origin.startswith("https://"):
            return "denied", {}
        url = route.origin.rstrip("/") + route.path_template
        body = dict(payload)
        kwargs: dict[str, Any] = {
            "headers": {"Authorization": f"Bearer {access_token}"},
            "timeout": route.timeout_s,
            "follow_redirects": False,
        }
        if route.method == "GET":
            kwargs["params"] = body
        else:
            kwargs["json"] = body
        try:
            resp = self._client.request(route.method, url, **kwargs)
        except Exception:
            return "denied", {}
        return self._project(resp, route)

    @staticmethod
    def _project(resp: Any, route: ProviderRoute) -> tuple[str, dict[str, Any]]:
        status = int(getattr(resp, "status_code", 0))
        if status == 401:
            return "unauthorized", {}
        if 300 <= status < 400:  # a redirect is never followed and never trusted
            return "denied", {}
        content = getattr(resp, "content", b"") or b""
        if len(content) > route.max_bytes or not (200 <= status < 300):
            return "denied", {}
        try:
            data = resp.json()
        except Exception:
            return "denied", {}
        if not isinstance(data, dict):
            return "denied", {}
        return "ok", redact_secrets(data)


__all__ = ["HttpProviderEgress"]
