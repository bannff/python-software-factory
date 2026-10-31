---
name: repo-graph-query
description: Queries the local structural index of this repo's Python source for imports, callers, and symbol locations. Use when scoping refactor blast radius instead of grepping.
---

# Repo Graph Query Skill

Teaches agents to query the local structural index of this repo's own Python
source instead of grepping fresh every time, when scoping a refactor's blast
radius (imports, callers, symbol locations) across components/bases/projects.

This indexes THE FACTORY'S OWN source code for repo development. It is
unrelated to the `graph` brick, which is a runtime capability for products
built on this repo (RL findings, telemetry, entities) — that brick has no
knowledge of this repo's own Python structure.

## When to use this instead of grep

- "What imports this module/symbol, across the whole repo?" → `find-importers`
- "Where is this function/class defined?" → `find-symbol`
- "What functions call this one, and where?" → `find-callers`
- Anything broader (semantic understanding, string content, non-Python files) → still use `grep_search`/`context-gatherer`. This tool only knows imports, symbol definitions, and call edges from `ast` parsing — it does not understand string literals, comments, or runtime behavior.

## Commands

Run from the repo root:

```bash
python .agents/scripts/build-repo-graph.py build
python .agents/scripts/build-repo-graph.py find-symbol <name>
python .agents/scripts/build-repo-graph.py find-importers <module-or-name>
python .agents/scripts/build-repo-graph.py find-callers <function-name>
```

- `build` regenerates `.agents/.repo-graph/graph.sqlite` from scratch (stdlib-only, ~a few seconds for the whole repo). Rebuild after a session with significant file changes — the index is a snapshot, not live.
- `find-importers` matches both absolute (`from factory.mcp_utils import event_bus`) and relative (`from .event_bus import ...` / `from . import event_bus`) import styles automatically.
- `find-callers` matches by function/method name only (not fully-qualified path) — a common name can return call sites across unrelated bricks; cross-check the file path in the output against the brick you actually care about.
- Output is exact matches only — no fuzzy/semantic search. If a query returns nothing, the symbol may be dynamically constructed (e.g. `getattr`, string-based dispatch) and won't show up; fall back to grep for those cases.

## Known limitations (do not over-trust the output)

- Call-edge detection matches on the called name only, not the actual bound object — `foo.bar()` and `baz.bar()` both record callee `bar`. Good for "does anything call a function named X," not proof of a specific object's method being called.
- No cross-repo resolution — this only sees `components/`, `bases/`, `projects/` inside this workspace root.
- The index goes stale the moment files change after a `build`. If you're not sure it's fresh, rebuild before trusting a "not found" result.
