"""Local (in-process, non-network) embedder for the KB brick.

M7.7 scoping consult (`8382bf2f`): "Memory + KB onto the one persistent
graph" needs "one shared embedding space," which means both bricks point
at the SAME kind of local model — not a shared Protocol import (doctrine
forbids reaching into another brick's runtime internals; each brick gets
its own adapter implementing its own ``KBEmbedder``/``MemoryEmbedder``
port). This is the KB-side twin of
``factory.memory.runtime.embedding_local.LlamaCppEmbedder`` — same shape,
same fallback contract, kept brick-local per doctrine.
"""
from __future__ import annotations

import hashlib
import os
import re
from typing import Any

_WORD_RE = re.compile(r"[a-z0-9]+")
_FALLBACK_DIMS = 256


def _keyword_hash_vector(text: str, dims: int) -> list[float]:
    """Deterministic bag-of-words hash vector — a real fallback, not a stub."""
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


class LocalKBEmbedder:
    """Local GGUF embedder via ``llama-cpp-python``, keyword fallback.

    ``model_path`` defaults to ``KB_LOCAL_EMBED_MODEL`` — the same GGUF
    file the memory brick's ``MEMORY_LOCAL_EMBED_MODEL`` should point at,
    for one shared embedding space, per the consult's ruling.
    """

    def __init__(self, model_path: str | None = None) -> None:
        self._model_path = model_path or os.environ.get("KB_LOCAL_EMBED_MODEL", "")
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
        return self._model is not None

    @property
    def model_path(self) -> str:
        return self._model_path

    @property
    def load_error(self) -> str | None:
        return self._load_error

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self._model is not None:
            vectors = [self._model.embed(text) for text in texts]
            return [v if v and isinstance(v[0], float) else v[0] for v in vectors]
        return [_keyword_hash_vector(text, self._dims) for text in texts]

    @property
    def dimensions(self) -> int:
        return self._dims


__all__ = ["LocalKBEmbedder"]
