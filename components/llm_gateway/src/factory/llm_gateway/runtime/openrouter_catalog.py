"""Live OpenRouter model catalog with a durable cache and offline fallback.

The picker previously offered exactly one OpenRouter model: the env default.
This adapter fetches ``GET {OPENROUTER_BASE_URL}/models`` with the configured
key (read only inside the request; never returned), caches the safe id list
(plus per-token pricing) under ``.storage``, and falls back to the last cache
when offline. Only model identifiers and per-token USD pricing cross the
boundary — no endpoint, key, or raw payload.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from .chat_profile import resolve_chat_profile

_MODEL_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*/[a-z0-9][a-z0-9._:-]*$", re.IGNORECASE)
_MAX_MODELS = 2000
_TTL_SECONDS = 6 * 60 * 60
_TIMEOUT = httpx.Timeout(10.0)
_CACHE_SCHEMA_VERSION = 2  # v2 adds pricing; a v1 (or unmarked) cache lacks it and must re-fetch.


@dataclass(frozen=True, slots=True)
class ModelPricing:
    """Per-token USD pricing for one model (OpenRouter's own units)."""

    prompt_usd_per_token: float
    completion_usd_per_token: float


def cache_path() -> Path:
    return Path(os.getenv(
        "COMPANION_X_MODEL_CATALOG_CACHE", "./.storage/openrouter-models.json",
    ))


def openrouter_models(*, refresh: bool = False) -> tuple[str, ...]:
    """Return provider-native OpenRouter model ids; empty when unavailable."""
    return _catalog(refresh=refresh)[0]


def openrouter_pricing(*, refresh: bool = False) -> dict[str, ModelPricing]:
    """Return per-model pricing for the ids in :func:`openrouter_models`."""
    return _catalog(refresh=refresh)[1]


def _catalog(*, refresh: bool) -> tuple[tuple[str, ...], dict[str, ModelPricing]]:
    cached = _read_cache()
    if cached is not None and not refresh and not _stale(cached[0]):
        return cached[1], cached[2]
    try:
        models, pricing = _fetch()
    except (httpx.HTTPError, ValueError, OSError):
        return (cached[1], cached[2]) if cached is not None else ((), {})
    _write_cache(models, pricing)
    return models, pricing


def _fetch() -> tuple[tuple[str, ...], dict[str, ModelPricing]]:
    profile = resolve_chat_profile("openrouter/catalog")
    api_key = os.getenv(profile.api_key_env or "", "").strip()
    if not profile.base_url or not api_key:
        raise ValueError("openrouter catalog unavailable")
    headers = {"Authorization": f"Bearer {api_key}", **profile.default_headers}
    with httpx.Client(timeout=_TIMEOUT) as client:
        response = client.get(f"{profile.base_url.rstrip('/')}/models", headers=headers)
    response.raise_for_status()
    payload = response.json()
    rows = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ValueError("openrouter catalog malformed")
    valid = [
        row for row in rows
        if isinstance(row, dict) and isinstance(row.get("id"), str)
        and _MODEL_RE.fullmatch(row["id"])
    ]
    ids = sorted({str(row["id"]) for row in valid})
    if not ids:
        raise ValueError("openrouter catalog empty")
    pricing = {
        row["id"]: parsed for row in valid
        if (parsed := _parse_pricing(row.get("pricing"))) is not None
    }
    return tuple(ids[:_MAX_MODELS]), pricing


def _parse_pricing(raw: object) -> ModelPricing | None:
    if not isinstance(raw, dict):
        return None
    try:
        prompt = float(raw.get("prompt", "nan"))
        completion = float(raw.get("completion", "nan"))
    except (TypeError, ValueError):
        return None
    if prompt != prompt or completion != completion or prompt < 0 or completion < 0:
        return None  # NaN or negative — malformed, drop rather than mislead
    return ModelPricing(prompt_usd_per_token=prompt, completion_usd_per_token=completion)


def _read_cache() -> tuple[float, tuple[str, ...], dict[str, ModelPricing]] | None:
    path = cache_path()
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        fetched_at = float(document["fetched_at"])
        models = tuple(
            item for item in document["models"]
            if isinstance(item, str) and _MODEL_RE.fullmatch(item)
        )
        if document.get("schema_version") != _CACHE_SCHEMA_VERSION:
            # Pre-pricing cache: still a valid models-only offline fallback,
            # but never "fresh" — force a live re-fetch whenever reachable
            # so pricing populates without the owner needing to know to
            # manually force one.
            fetched_at = 0.0
            raw_pricing: dict[str, object] = {}
        else:
            raw_pricing = document.get("pricing", {})
        pricing = {
            model_id: parsed for model_id, entry in raw_pricing.items()
            if model_id in models and (parsed := _parse_pricing(entry)) is not None
        }
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return (fetched_at, models, pricing) if models else None


def _write_cache(models: tuple[str, ...], pricing: dict[str, ModelPricing]) -> None:
    path = cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "schema_version": _CACHE_SCHEMA_VERSION,
            "fetched_at": time.time(), "models": list(models),
            "pricing": {
                model_id: {
                    "prompt": entry.prompt_usd_per_token,
                    "completion": entry.completion_usd_per_token,
                }
                for model_id, entry in pricing.items()
            },
        }, separators=(",", ":")), encoding="utf-8")
    except OSError:
        return


def _stale(fetched_at: float) -> bool:
    return time.time() - fetched_at > _TTL_SECONDS


__all__ = ["ModelPricing", "cache_path", "openrouter_models", "openrouter_pricing"]
