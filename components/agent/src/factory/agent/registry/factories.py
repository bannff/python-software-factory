"""Factory registry for workflow-kind registrations.

Resolves string keys carried in registration dicts (``kind=workflow``,
``factory='<key>'``) to deterministic callables that produce a
``list[dict]`` of Strands ``WorkflowManager`` tasks.  Pure functions,
deterministic over context (``vuln_class`` etc.) — Hypothesis property
tested across all 6 vuln_classes in ``test_factories.py``.

Why a string registry key instead of an embedded callable?
The meta-architect's Option A (memory ``33b12ebb``) keeps the
registration dict pure data so it can be JSON-dumped, diffed, and
loaded from disk without import-time side effects.  The manifest
compiler (``runtime/execution_manifest/compile_workflow.py``) calls
``get_factory(name)`` to resolve the key just before workflow create.

bd python-factory-uffq: ``WorkflowConfig._factory_must_resolve``
validator imports ``known_factories`` lazily to keep the registry
known set computable BEFORE ``defaults_code_scan`` instantiates the
canary ``SAST_TARGETED_REGISTRATION``. We declare ``FACTORY_REGISTRY``
keys at module top, then defer the actual callable lookup to
``get_factory`` which imports ``defaults_code_scan`` on demand.
"""
from __future__ import annotations

from typing import Any, Callable, Dict

#: A factory takes the runtime context (which carries ``vuln_class``,
#: ``run_id``, etc.) and returns the rendered task list. Keep these
#: pure — no I/O, no side effects, deterministic over context.
FactoryFn = Callable[[Dict[str, Any]], list[Dict[str, Any]]]


# Declare keys eagerly so ``known_factories()`` is callable from the
# WorkflowConfig validator before any defaults_*.py module is fully
# imported. Callables are resolved lazily inside ``get_factory``.
_FACTORY_KEYS: tuple[str, ...] = (
    "sast_targeted", "sandbox_setup",
    "sast_open", "dast_open",
)


def known_factories() -> list[str]:
    """Return the list of registered factory keys, sorted.

    Callable from the ``WorkflowConfig`` model validator at
    registration-instantiation time, before defaults_*.py modules
    have fully imported. The set is fixed at this module's import
    time; new factories must be added to ``_FACTORY_KEYS``.
    """
    return sorted(_FACTORY_KEYS)


def get_factory(name: str) -> FactoryFn:
    """Resolve a factory by string key.

    Imports ``defaults_code_scan`` (or other defaults files) lazily
    so this module stays cycle-free during the agent brick's import
    storm. Raises ``KeyError`` for unknown keys.
    """
    if name not in _FACTORY_KEYS:
        raise KeyError(
            f"Unknown factory key: {name!r}. "
            f"Known: {known_factories()}"
        )
    if name == "sast_targeted":
        from .defaults_code_scan import build_sast_targeted_tasks
        return lambda ctx: build_sast_targeted_tasks(
            str(ctx.get("vuln_class", ""))
        )
    if name == "sandbox_setup":
        from .defaults_sandbox_graph import build_sandbox_setup_tasks
        # ctx ignored — sandbox-setup factory is a pure constant
        return lambda _ctx: build_sandbox_setup_tasks()
    if name == "sast_open":
        from .defaults_sast_open import build_sast_open_tasks
        # ctx ignored — sast_open factory is a pure constant (no vuln_class)
        return lambda _ctx: build_sast_open_tasks()
    if name == "dast_open":
        from .defaults_dast_open import build_dast_open_tasks
        # ctx ignored — dast_open factory is a pure constant (no vuln_class)
        return lambda _ctx: build_dast_open_tasks()
    raise KeyError(f"Unknown factory key: {name!r}")


# Back-compat: tests / external callers reading ``FACTORY_REGISTRY``
# get a property-like view backed by lazy resolution. Implemented as
# a simple dict-of-callables built on first access; safe because
# resolution is idempotent and the underlying ``defaults_code_scan``
# is imported by then.
def _build_registry() -> Dict[str, FactoryFn]:
    return {k: get_factory(k) for k in _FACTORY_KEYS}


class _LazyRegistry(dict):
    """Dict-like view over factory keys; resolves callables lazily."""

    def __init__(self) -> None:
        super().__init__({k: None for k in _FACTORY_KEYS})

    def __getitem__(self, key: str) -> FactoryFn:
        return get_factory(key)

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def __iter__(self):
        return iter(_FACTORY_KEYS)

    def keys(self):
        return list(_FACTORY_KEYS)


FACTORY_REGISTRY: Dict[str, FactoryFn] = _LazyRegistry()  # type: ignore[assignment]
