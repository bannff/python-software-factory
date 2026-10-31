"""Persistence-contract property tests (bd python-factory-evra+0s6w).

Pins the SAST/DAST persistence gap closure (impl mem
``cae16323-30d5-4251-b354-a23f0131171f``) so a future regression
fails fast.

Properties (read directly from registry/ + skills/ source — no private state):
  P1. ``idor-validate/SKILL.md`` PHASE 3 persists ``entity_type='Finding'``;
      ``ValidatedFinding`` never reappears (RL F1 keys on canonical label).
  P2. ``dast-open-scan/SKILL.md`` PHASE 4 persists ``ProvenExploit``;
      ``ConfirmedVuln`` is gone from both dast/sast-open-scan skills.
  P3. ``_VALIDATOR_TOOLS`` (sast_open + code_scan) and ``_DAST_TOOLS``
      (dast_open) include ``graph_add_entity`` — workflow-path persistence
      flows through the graph node tool filter.
  P4. Hybrid + swarm ``_CONSOLIDATOR_PROMPT`` specify
      ``entity_type='Finding'`` (graph/swarm prompt-side fix).
  P5. Workflow-path tool list entries are bare Python identifiers
      (hybrid/swarm dotted form is by design — excluded).
  P6. ``entity_type='ValidatedFinding'`` regression scan across
      ``registry/`` + ``skills/`` returns zero matches.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

from hypothesis import given, settings, strategies as st

_AGENT_SRC = Path(__file__).resolve().parents[3] / "src" / "factory" / "agent"
_REGISTRY = _AGENT_SRC / "registry"
_SKILLS = _AGENT_SRC / "skills"

_IDOR_VAL = _SKILLS / "idor-validate" / "SKILL.md"
_DAST_OPEN = _SKILLS / "dast-open-scan" / "SKILL.md"
_SAST_OPEN_SK = _SKILLS / "sast-open-scan" / "SKILL.md"
_DEF_SAST = _REGISTRY / "defaults_sast_open.py"
_DEF_DAST = _REGISTRY / "defaults_dast_open.py"
_DEF_CODE_SCAN = _REGISTRY / "defaults_code_scan.py"
_DEF_HYBRID = _REGISTRY / "defaults_code_scan_hybrid.py"
_DEF_SWARM = _REGISTRY / "defaults_code_scan_swarm.py"

# Quote-flavour-tolerant entity_type literal scanners.
_RE_FINDING = re.compile(r"""entity_type=['"]Finding['"]""")
_RE_VALIDATED = re.compile(r"""entity_type=['"]ValidatedFinding['"]""")
_RE_PROVEN = re.compile(r"""entity_type=['"]ProvenExploit['"]""")
_RE_CONFIRMED = re.compile(r"""entity_type=['"]ConfirmedVuln['"]""")


def _read(p: Path) -> str:
    assert p.is_file(), f"missing fixture: {p}"
    return p.read_text(encoding="utf-8")


def _value(src: str, name: str) -> object:
    """Resolve module-level ``<name> = <literal>`` via AST literal_eval."""
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found as module-level assignment")


def _str_list(src: str, name: str) -> list[str]:
    out = _value(src, name)
    assert isinstance(out, list) and all(isinstance(x, str) for x in out), name
    return out


# --- P1: idor-validate persists Finding, never ValidatedFinding ------


def test_idor_validate_persists_finding_label() -> None:
    text = _read(_IDOR_VAL)
    assert _RE_FINDING.search(text), (
        "idor-validate PHASE 3 lost entity_type='Finding' — RL F1 falls "
        "back to 0 (impl mem cae16323)."
    )


def test_idor_validate_no_validated_finding_label() -> None:
    text = _read(_IDOR_VAL)
    assert not _RE_VALIDATED.search(text), (
        "idor-validate regressed to entity_type='ValidatedFinding' — F1 "
        "keys on the canonical 'Finding' label."
    )


# --- P2: DAST persists ProvenExploit; ConfirmedVuln gone -------------


def test_dast_open_persists_proven_exploit_label() -> None:
    text = _read(_DAST_OPEN)
    assert _RE_PROVEN.search(text), (
        "dast-open-scan PHASE 4 lost entity_type='ProvenExploit'."
    )


def test_dast_open_no_confirmed_vuln_label() -> None:
    text = _read(_DAST_OPEN)
    assert not _RE_CONFIRMED.search(text), (
        "dast-open-scan regressed to entity_type='ConfirmedVuln' — should "
        "be ProvenExploit (impl mem cae16323)."
    )


def test_sast_open_skill_no_confirmed_vuln_reference() -> None:
    """Collateral fix: PHASE 0 must not reference deprecated ConfirmedVuln."""
    text = _read(_SAST_OPEN_SK)
    assert "ConfirmedVuln" not in text, (
        "sast-open-scan re-introduced ConfirmedVuln (collateral bd-evra fix)."
    )


# --- P3: validator/tester tool lists include graph_add_entity --------


def test_sast_open_validator_tools_include_graph_add_entity() -> None:
    assert "graph_add_entity" in _str_list(_read(_DEF_SAST), "_VALIDATOR_TOOLS")


def test_code_scan_validator_tools_include_graph_add_entity() -> None:
    assert "graph_add_entity" in _str_list(
        _read(_DEF_CODE_SCAN), "_VALIDATOR_TOOLS"
    )


def test_dast_open_tester_tools_include_graph_add_entity() -> None:
    assert "graph_add_entity" in _str_list(_read(_DEF_DAST), "_DAST_TOOLS")


# --- P4: hybrid + swarm consolidator prompts specify Finding ---------


def test_code_scan_hybrid_consolidator_prompt_specifies_finding() -> None:
    p = str(_value(_read(_DEF_HYBRID), "_CONSOLIDATOR_PROMPT"))
    assert _RE_FINDING.search(p), (
        "hybrid _CONSOLIDATOR_PROMPT lost entity_type='Finding'."
    )


def test_code_scan_swarm_consolidator_prompt_specifies_finding() -> None:
    p = str(_value(_read(_DEF_SWARM), "_CONSOLIDATOR_PROMPT"))
    assert _RE_FINDING.search(p), (
        "swarm _CONSOLIDATOR_PROMPT lost entity_type='Finding'."
    )


# --- P5: bare-name discipline on workflow-path tool lists ------------

_WORKFLOW_TOOL_LISTS: list[tuple[Path, str]] = [
    (_DEF_SAST, "_SCAN_TOOLS"),
    (_DEF_SAST, "_HIERARCHY_TOOLS"),
    (_DEF_SAST, "_CONSOLIDATOR_TOOLS"),
    (_DEF_SAST, "_VALIDATOR_TOOLS"),
    (_DEF_DAST, "_DAST_TOOLS"),
    (_DEF_CODE_SCAN, "_SCAN_TOOLS"),
    (_DEF_CODE_SCAN, "_CONSOLIDATOR_TOOLS"),
    (_DEF_CODE_SCAN, "_VALIDATOR_TOOLS"),
]


@settings(max_examples=50, deadline=None)
@given(idx=st.integers(min_value=0, max_value=len(_WORKFLOW_TOOL_LISTS) - 1))
def test_workflow_path_tool_lists_use_bare_python_identifiers(idx: int) -> None:
    """Property: every entry in a workflow-path tool list literal is a
    bare Python identifier. The graph node tool filter keys on
    ``TOOL_SPEC.name``; dotted prefixes break the filter (bd-42dz)."""
    path, name = _WORKFLOW_TOOL_LISTS[idx]
    for entry in _str_list(_read(path), name):
        assert "." not in entry, (
            f"{path.name}.{name}: '{entry}' has a dotted prefix — "
            "workflow filter expects bare names (bd-42dz contract)."
        )
        assert entry.isidentifier(), (
            f"{path.name}.{name}: '{entry}' is not a Python identifier."
        )


# --- P6: zero ValidatedFinding regression in registry + skills -------


def test_no_validated_finding_in_registry_or_skills() -> None:
    offenders: list[str] = []
    for root in (_REGISTRY, _SKILLS):
        for path in list(root.rglob("*.py")) + list(root.rglob("*.md")):
            if not path.is_file():
                continue
            if _RE_VALIDATED.search(path.read_text(encoding="utf-8")):
                offenders.append(str(path.relative_to(_AGENT_SRC)))
    assert not offenders, (
        "entity_type='ValidatedFinding' regression in: " + ", ".join(offenders)
    )
