"""Pre-flight validation for graph/swarm/workflow launch context.

Resolves templated skill references against the on-disk skill
inventory and refuses to launch if a referenced skill is missing.
Pure stdlib function — callable from any launcher (run_graph.py,
invoke_graph, invoke_graph_async).

Static refs in graphs/swarms are gated at test time by
``test_skills_inventory_properties.py``. For workflow-kind configs
the factory pre-renders ``{{vuln_class}}``; the validator scans the
rendered prompts for static skill refs (bd python-factory-a4h7).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Sequence

from ..authoring.roots import packaged_skills_root, resolve_root

# Templated skill ref forms in migrated prompts:
#   1. ``Use the `{{var}}-suffix` skill``  (backticked)
#   2. ``Use the {{var}}-suffix skill``    (bare)
# Captures the whole template string (including the ``{{var}}``).
# Only TEMPLATED refs are returned; static refs are caught at test
# time by test_skills_inventory_properties.py — except for
# workflow-kind configs, where the factory has already pre-rendered
# variables, so the validator scans rendered prompts via
# ``_STATIC_BACKTICK`` below.
_TEMPLATED_BACKTICK = re.compile(
    r"Use the `(\{\{[^}]+\}\}-[a-z][a-z0-9-]*)` skill"
)
_TEMPLATED_BARE = re.compile(
    r"Use the (\{\{[^}]+\}\}-[a-z][a-z0-9-]*) skill"
)
# Static (already-rendered) skill ref forms — used for workflow
# configs whose factory pre-renders {{vuln_class}} before the
# validator sees the prompt. Same surface as the templated regex
# without the ``{{...}}`` group.
_STATIC_BACKTICK = re.compile(
    r"Use the `([a-z][a-z0-9-]*)` skill"
)
# Single ``{{var}}`` substitution. Same shape as
# executors/_template.py:inject_variables — keep in sync.
_VAR_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


def skills_dir() -> Path:
    """Canonical packaged (built-in) skills directory; see ``skills_roots``."""
    return packaged_skills_root()


def skills_roots() -> tuple[Path, ...]:
    """Every root a skill id may live in: packaged built-ins, then the user root."""
    packaged, user = packaged_skills_root(), resolve_root("skills").path
    return (packaged,) if user == packaged else (packaged, user)


def _extract_templated_refs(text: str) -> list[str]:
    """Return every templated skill ref (preserves duplicates)."""
    refs: list[str] = []
    refs.extend(_TEMPLATED_BACKTICK.findall(text))
    refs.extend(_TEMPLATED_BARE.findall(text))
    return refs


def _resolve_template(template: str, context: dict[str, Any]) -> str:
    """Substitute ``{{var}}`` placeholders from context.

    Mirrors ``executors/_template.py:inject_variables``. Missing
    variables are left as-is — the caller surfaces them via
    ``Missing required context variable``.
    """
    result = template
    for key, value in context.items():
        result = re.sub(
            r"\{\{\s*" + re.escape(key) + r"\s*\}\}", str(value), result,
        )
    return result


def _iter_prompts(
    config: dict[str, Any], context: dict[str, Any] | None = None,
) -> list[str]:
    """Yield every system_prompt across graph nodes / swarm agents / workflow tasks.

    Graph configs use ``nodes``; swarm configs use ``agents``. We
    scan both — meta-architect upgraded swarm coverage from P3 to
    P2 because ``defaults_code_scan_swarm.py`` has live templated
    refs invoked today by ``invoke_swarm``/``invoke_swarm_async``.

    Workflow configs (``kind == "workflow"``) carry their tasks via
    a string ``factory`` key resolved through
    ``registry/factories.py``. We invoke the factory with the
    runtime context so its rendered prompts go through the same
    ``{{var}}-suffix`` skill-resolution pass below. The factory
    must be pure-deterministic over the context — Hypothesis-tested
    in ``test_factories.py``. See bd python-factory-a4h7.
    """
    out: list[str] = []
    for node in config.get("nodes", []) or []:
        prompt = node.get("system_prompt") if isinstance(node, dict) else None
        if isinstance(prompt, str):
            out.append(prompt)
    for agent in config.get("agents", []) or []:
        prompt = agent.get("system_prompt") if isinstance(agent, dict) else None
        if isinstance(prompt, str):
            out.append(prompt)
    if config.get("kind") == "workflow" and config.get("factory"):
        try:
            from .factories import get_factory
            factory = get_factory(str(config["factory"]))
            for task in factory(context or {}):
                p = task.get("system_prompt") if isinstance(task, dict) else None
                if isinstance(p, str):
                    out.append(p)
        except Exception:
            # Don't crash validation on factory errors — they surface
            # via the missing-context-var or missing-skill paths.
            pass
    return out


def validate_launch_context(
    config: dict[str, Any] | Any,
    context: dict[str, Any],
    skills_dirs: Sequence[Path] | None = None,
) -> list[str]:
    """Return error strings; empty list = OK to launch.

    ``config`` may be a plain dict (legacy) or a Pydantic
    ``RegistryConfig`` model (post-uffq). Models are dumped to dict
    once on entry; rest of validator stays dict-shaped.

    ``skills_dirs`` overrides the layered roots a skill id may live in;
    the default is ``skills_roots()`` (built-ins + user root).
    """
    if hasattr(config, "model_dump"):
        config = config.model_dump(by_alias=True)
    errors: list[str] = []
    roots = tuple(skills_dirs) if skills_dirs is not None else skills_roots()

    def _on_disk(skill_id: str) -> bool:
        return any((root / skill_id / "SKILL.md").is_file() for root in roots)

    # 1. Required context_vars present.
    required: list[str] = list(config.get("context_vars", []) or [])
    for var in required:
        val = context.get(var) if var in context else None
        # Treat whitespace-only strings as empty — the launcher must
        # refuse to spawn rather than let the LLM hit a bogus skill
        # ref like ``   -code-scan`` mid-execution.
        if val is None or val == "" or (
            isinstance(val, str) and not val.strip()
        ):
            errors.append(f"Missing required context variable: {var}")

    is_workflow = config.get("kind") == "workflow"

    # 2. Templated + (for workflow-kind) static skill refs resolve on disk.
    seen: set[tuple[str, str]] = set()  # (template, resolved) dedup
    for prompt in _iter_prompts(config, context):
        for template in _extract_templated_refs(prompt):
            resolved = _resolve_template(template, context)
            if resolved == template or "{{" in resolved:
                # Template still has unresolved placeholders. The
                # missing-context-var error above already covers
                # the user-facing message; skip silently here.
                continue
            key = (template, resolved)
            if key in seen:
                continue
            seen.add(key)
            if not _on_disk(resolved):
                # Surface which context var drove the (failed)
                # resolution so the user knows what to fix.
                vars_in = _VAR_RE.findall(template)
                pairs = ", ".join(
                    f"{v}='{context.get(v, '')}'" for v in vars_in
                )
                errors.append(
                    f"Skill `{resolved}` not found on disk "
                    f"(template `{template}`, {pairs})"
                )
        if is_workflow:
            for resolved in _STATIC_BACKTICK.findall(prompt):
                key2 = ("<workflow-static>", resolved)
                if key2 in seen:
                    continue
                seen.add(key2)
                if not _on_disk(resolved):
                    errors.append(
                        f"Skill `{resolved}` not found on disk "
                        f"(workflow factory rendered)"
                    )

    return errors
