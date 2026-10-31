"""Legacy import alias support for ChromaDB adapter.

Provides backwards compatibility for tests that use kb_module.* paths.
"""

import sys
import types


def install_legacy_import_aliases() -> None:
    """Install `kb_module.*` aliases used by legacy tests.

    The test suite patches `kb_module.runtime.retrieval.chroma.chromadb` while
    instantiating `factory.kb.runtime.retrieval.chroma.ChromaVectorStore`.
    Making the module importable via the legacy path ensures the patch affects
    this module's `chromadb` symbol.
    """
    if "kb_module" not in sys.modules:
        kb_module = types.ModuleType("kb_module")
        kb_module.__path__ = []
        sys.modules["kb_module"] = kb_module
    else:
        kb_module = sys.modules["kb_module"]

    if "kb_module.engine" not in sys.modules:
        engine = types.ModuleType("kb_module.engine")
        engine.__path__ = []
        sys.modules["kb_module.engine"] = engine
        setattr(kb_module, "engine", engine)
    else:
        engine = sys.modules["kb_module.engine"]

    if "kb_module.runtime.retrieval" not in sys.modules:
        retrieval = types.ModuleType("kb_module.runtime.retrieval")
        retrieval.__path__ = []
        sys.modules["kb_module.runtime.retrieval"] = retrieval
        setattr(engine, "retrieval", retrieval)
    else:
        retrieval = sys.modules["kb_module.runtime.retrieval"]

    # Import the main chroma module to register it
    from factory.kb.runtime.retrieval import chroma
    sys.modules["kb_module.runtime.retrieval.chroma"] = chroma
    setattr(retrieval, "chroma", chroma)
