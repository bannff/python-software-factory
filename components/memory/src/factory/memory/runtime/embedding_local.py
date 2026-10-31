"""Local (in-process, non-network) embedder for the memory brick.

M7.7 scoping consult (`8382bf2f`): the owner rule is embeddings-only,
never inference, and never a network call-out (``LLMGatewayEmbedder``
is Bedrock/OpenAI — the opposite of "local"). This adapter tries a real
local GGUF embedding model via ``llama-cpp-python`` when both the
package and a model file are present; otherwise it degrades to a
deterministic keyword-hash vector rather than silently returning zeros
or raising — callers can check ``is_semantic`` to know which mode is
live instead of being told a fallback vector is a real embedding.
"""
from __future__ import annotations

import hashlib
import os
import re
from typing import Any

_WORD_RE = re.compile(r"[a-z0-9]+")
_FALLBACK_DIMS = 256


def _keyword_hash_vector(text: str, dims: int) -> list[float]:
    """Deterministic bag-of-words hash vector — a real fallback, not a stub.

    Same text -> same vector always, so cosine similarity is meaningful
    for near-duplicate detection even without a semantic model.
    """
    vector = [0.0] * dims
    words = _WORD_RE.findall(text.lower())
    if not words:
        return vector
    for word in words:
        digest = hashlib.sha256(word.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dims
        vector[index] += 1.0
    norm = sum(v * v for v in vector) ** 0.5
    return [v / norm for v in vector] if norm > 0 else vector


class LlamaCppEmbedder:
    """Local GGUF embedder via ``llama-cpp-python``, keyword fallback.

    ``model_path`` defaults to ``MEMORY_LOCAL_EMBED_MODEL`` (e.g. a
    Qwen3-Embedding-0.6B GGUF). When the package is missing or the file
    does not exist, ``embed`` uses the keyword-hash fallback and
    ``is_semantic`` reports ``False`` so callers can surface that honestly
    (e.g. a "degraded" status on the Embeddings settings row) instead of
    claiming semantic search is live when it is not.
    """

    def __init__(self, model_path: str | None = None) -> None:
        self._model_path = model_path or os.environ.get("MEMORY_LOCAL_EMBED_MODEL", "")
        self._model: Any = None
        self._dims = _FALLBACK_DIMS
        self._load_error: str | None = None
        self._try_load()

    def _try_load(self) -> None:
        if not self._model_path or not os.path.isfile(self._model_path):
            self._load_error = "model_file_not_found"
            return
        try:
            from llama_cpp import Llama
        except ImportError:
            self._load_error = "llama_cpp_not_installed"
            return
        try:
            self._model = Llama(model_path=self._model_path, embedding=True, verbose=False)
            probe = self._model.embed("probe")
            self._dims = len(probe) if isinstance(probe, list) and probe and isinstance(probe[0], float) else len(probe[0])
        except Exception as exc:  # pragma: no cover - depends on native lib
            self._load_error = f"load_failed:{exc}"
            self._model = None

    @property
    def is_semantic(self) -> bool:
        """True iff a real local model is loaded (not the hash fallback)."""
        return self._model is not None

    @property
    def model_path(self) -> str:
        """Configured model path (empty string if none was set)."""
        return self._model_path

    @property
    def load_error(self) -> str | None:
        """Reason the semantic model is not active, or ``None`` if it is."""
        return self._load_error

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self._model is not None:
            vectors = [self._model.embed(text) for text in texts]
            return [v if isinstance(v[0], float) else v[0] for v in vectors]
        return [_keyword_hash_vector(text, self._dims) for text in texts]

    @property
    def dimensions(self) -> int:
        return self._dims


__all__ = ["LlamaCppEmbedder"]
