"""Env-driven ``ContextOffloader`` plugin wiring for the chat build (#107).

``.env.example`` documents ``STRANDS_OFFLOAD_*``; this module is the
missing seam: when ``STRANDS_OFFLOAD_BACKEND`` is set (``file`` |
``memory`` | ``s3``), one ``ContextOffloader`` plugin is built with the
env's token thresholds and mounts on the thread agent. Unset → ``None``
→ default off. Backends map to official strands storage classes
(``LocalFileStorage``/``S3Storage``/``InMemoryStorage``); the legacy
offloader ``FileStorage`` is deprecated upstream.
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_BACKENDS = ("file", "memory", "s3")


def offloader_plugin_from_env() -> Any | None:
    """Build one ``ContextOffloader`` from STRANDS_OFFLOAD_* env, or None.

    Unset backend → default off (no plugin). Unknown backend → loud
    ValueError (misconfiguration, never a silent fallback).
    """
    from strands.vended_plugins.context_offloader import ContextOffloader

    backend = os.getenv("STRANDS_OFFLOAD_BACKEND", "").strip().lower()
    if not backend:
        return None
    if backend not in _BACKENDS:
        raise ValueError(f"unknown STRANDS_OFFLOAD_BACKEND: {backend!r}")
    kwargs: dict[str, Any] = {
        "max_result_tokens": _env_int("STRANDS_OFFLOAD_MAX_TOKENS", 8_000),
        "preview_tokens": _env_int("STRANDS_OFFLOAD_PREVIEW_TOKENS", 2_500),
        "include_retrieval_tool": True,
    }
    if backend == "file":
        from strands.storage import LocalFileStorage
        kwargs["storage"] = LocalFileStorage(
            os.getenv("STRANDS_OFFLOAD_DIR", "./.storage/offloaded"),
        )
    elif backend == "s3":
        from strands.storage import S3Storage
        bucket = os.getenv("STRANDS_OFFLOAD_BUCKET", "").strip()
        if not bucket:
            raise ValueError("STRANDS_OFFLOAD_BUCKET required for s3 offload")
        kwargs["storage"] = S3Storage(
            bucket, prefix=os.getenv("STRANDS_OFFLOAD_PREFIX", ""),
        )
    # memory → plugin default (InMemoryStorage resolved per agent)
    logger.info("backend=<%s> | context offloader mounted", backend)
    return ContextOffloader(**kwargs)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning("Ignoring non-integer %s=%r", name, raw)
        return default
    return value


def with_env_offloader(plugins: list[Any]) -> list[Any]:
    """Append the env-driven offloader (if any) to a plugin list."""
    plugin = offloader_plugin_from_env()
    return [*plugins, *([plugin] if plugin is not None else [])]


__all__ = ["offloader_plugin_from_env", "with_env_offloader"]
