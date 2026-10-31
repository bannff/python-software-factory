"""Compatibility shim for legacy imports used by tests.

This module aliases to `factory.kb.runtime.retrieval.chroma` so patching
`kb_module.runtime.retrieval.chroma.chromadb` affects the real implementation.
"""

from __future__ import annotations

import sys as _sys

from factory.kb.runtime.retrieval import chroma as _real

_sys.modules[__name__] = _real
