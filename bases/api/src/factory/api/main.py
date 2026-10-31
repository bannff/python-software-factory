"""API base entry point — starts uvicorn with the FastAPI application.

Usage:
    uv run <project-script-name>   # e.g. companion-api
    python -m factory.api.main     # direct invocation
"""

from __future__ import annotations

import os


def _promote_aws_profile() -> None:
    """Make the deployment's AWS profile authoritative over the dev shell.

    bd:python-factory-gtyb7. ``uv run --env-file`` yields to an
    already-exported ambient ``AWS_PROFILE`` (e.g. a developer's
    ``some-profile``), silently shadowing the deployment's ``AWS_PROFILE``
    declared in ``.env`` and pointing every boto3 default session at the
    wrong account (Bedrock chat, memory embeddings, KB, events, …). The
    namespaced ``COMPANION_X_AWS_PROFILE`` has no ambient collision, so
    promoting it to ``AWS_PROFILE`` HERE — at the composition root, before
    any brick import builds a boto3 default session — restores deployment
    authority. Env hygiene only; no brick logic (tenet 6 ok, mirrors the
    ``install_mcp_ui_redaction`` bootstrap below).
    """
    profile = os.environ.get("COMPANION_X_AWS_PROFILE")
    if profile:
        os.environ["AWS_PROFILE"] = profile


# Run at import time — before uvicorn imports ``create_app`` and before any
# brick / boto3 default session is constructed.
_promote_aws_profile()


def create_app():
    """Application factory for uvicorn."""
    # bd:python-factory-0x2jq (T9) — install mcp-ui body redaction
    # filter on stdlib loggers BEFORE the FastAPI app boots so any
    # tool_result content blocks containing UIResource bodies
    # (text/html, application/vnd.mcp-ui.*, text/uri-list) are
    # redacted to {uri, mimeType, size, sha256} before they reach
    # CloudWatch / OpenSearch / dev consoles. Idempotent.
    from factory.agent.runtime.observability.mcp_ui_redaction import (
        install_mcp_ui_redaction,
    )
    install_mcp_ui_redaction()

    from .interface import create_app as _create_app

    adapter_type = os.environ.get("FACTORY_API_ADAPTER", "rest")
    return _create_app(adapter_type)


def main() -> None:
    """Start the API server via uvicorn."""
    import uvicorn

    host = os.environ.get("FACTORY_API_HOST", "0.0.0.0")
    port = int(os.environ.get("FACTORY_API_PORT", "8000"))
    reload = os.environ.get("FACTORY_API_RELOAD", "false").lower() == "true"

    uvicorn.run(
        "factory.api.main:create_app",
        host=host,
        port=port,
        reload=reload,
        factory=True,
    )


if __name__ == "__main__":
    main()
