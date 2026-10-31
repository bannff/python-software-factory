"""Per-domain graph taxonomy definitions for the graph brick.

Each submodule is a self-contained domain extension that exposes:

* ``<DOMAIN>_NODE_TYPES`` — node-type dict
* ``<DOMAIN>_RELATIONSHIP_TYPES`` — relationship-type dict
* ``<DOMAIN>_CONVENTIONS`` — id-format / cross-domain notes dict
* ``register()`` — calls ``taxonomy_registry.register_extension``

Modules are pure data + a one-liner registration call; they MUST NOT
import each other. Auto-registration on import is intentionally omitted
so that tests calling ``reset_extensions`` get a clean slate — the
``register()`` function is the explicit hook.

Cross-brick consumers MUST import from
``factory.graph.runtime.taxonomies.<domain>`` or
``factory.graph.interface`` — never from the graph brick's internals.
"""
