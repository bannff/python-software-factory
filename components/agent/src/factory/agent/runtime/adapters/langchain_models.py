"""Per-model construction and targeted refresh for LangChain runtimes."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

ModelBuilder = Callable[[str], Any]


class LangChainModelCache:
    """Cache official model clients by non-secret model ID."""

    def __init__(
        self, initial_model: Any, default_model_id: str, builder: ModelBuilder | None,
    ) -> None:
        model_id = _model_id(default_model_id)
        self._default_model_id = model_id
        self._builder = builder
        self._models: dict[str, Any] = {model_id: initial_model}

    def effective_id(self, requested: str, persona_model: str) -> str:
        """Resolve request → persona → process default without reading secrets."""
        if requested:
            return _model_id(requested)
        if self._builder is not None and persona_model:
            return _model_id(persona_model)
        return self._default_model_id

    def get(self, model_id: str) -> Any:
        """Return or construct exactly one client for the selected ID."""
        selected = _model_id(model_id)
        if selected not in self._models:
            if self._builder is None:
                raise ValueError("chat model unavailable")
            self._models[selected] = self._builder(selected)
        return self._models[selected]

    def replace(self, model_id: str, model: Any | None = None) -> None:
        """Evict one model, optionally installing a refreshed client."""
        selected = _model_id(model_id)
        self._models.pop(selected, None)
        if model is not None:
            self._models[selected] = model

    def clear(self) -> None:
        self._models.clear()


def _model_id(value: str) -> str:
    selected = value.strip()
    if not selected or len(selected) > 256 or any(ord(char) < 32 for char in selected):
        raise ValueError("chat model unavailable")
    return selected


__all__ = ["LangChainModelCache", "ModelBuilder"]
