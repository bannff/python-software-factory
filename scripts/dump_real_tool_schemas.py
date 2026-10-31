"""Regenerate the real-schema fixture the palette's form tests run against.

    uv run python scripts/dump_real_tool_schemas.py

Anti-drift condition 4 of bd:3jcls.4 forbids a hand-written schema fixture:
the schema-to-form derivation has to be proved against something the repo
really ships. So the fixture is GENERATED from the live aggregator, and
``bases/mcp_server/test/.../test_catalog_fixture_matches_live_schemas.py``
fails if a brick's signature moves without regenerating it.

Tools were picked to cover every branch the derivation has: required strings,
a ``Literal`` enum, an ``int | None = None`` number, a ``str = "*"`` default,
a nullable object, and a no-argument tool.
"""

from __future__ import annotations

import json
from pathlib import Path

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "frontends/next-dashboard/__tests__/fixtures/real-tool-schemas.json"
)

#: ``qualified_name`` → brick. Kept small and purposeful, not a registry.
WANTED: dict[str, str] = {
    "cache_set": "cache",       # required str + str, plus int | None = None
    "cache_keys": "cache",      # str = "*" default, no required params
    "cache_stats": "cache",     # zero arguments
    "telemetry_record_log": "telemetry",  # Literal enum + nullable object
}


def collect() -> dict[str, object]:
    from factory.mcp_server.runtime.lazy_loader import LazyBrickLoader
    from factory.mcp_server.runtime.tool_catalog import build_tool_catalog

    class _Agg:
        def __init__(self, lazy: object) -> None:
            self._lazy = lazy

    loader = LazyBrickLoader()
    loader.set_available(sorted(set(WANTED.values())))
    catalog = build_tool_catalog(_Agg(loader), ["operational", "authoring"])
    by_name = {t["qualified_name"]: t for t in catalog["tools"]}
    missing = sorted(set(WANTED) - set(by_name))
    if missing:
        raise SystemExit(f"tools not found in live catalog: {missing}")
    return {
        "_generated_by": "scripts/dump_real_tool_schemas.py",
        "tools": [by_name[name] for name in WANTED],
    }


def main() -> None:
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    # NOT sort_keys: `properties` order is the tool's declaration order, which
    # is the order the generated form renders fields in.
    FIXTURE.write_text(json.dumps(collect(), indent=2) + "\n")
    print(f"wrote {FIXTURE}")


if __name__ == "__main__":
    main()
