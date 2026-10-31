"""Frozen-contract canaries for the domain brick (bd:python-factory-w7i8k).

Mirrors the spirit of ``test_canary_sdk_method_names_present`` — these
fail fast if a future edit breaks an architectural guarantee.

  #2 SRP CANARY:
     (a) PresentationManifest carries NO behaviour fields (presentation
         only) — its field set is disjoint from the persona/behaviour set.
     (b) The ``runtime/`` package source imports NO transport/MCP
         (``fastmcp``) — business logic stays transport-free.
  #3 ANTI-BRANCH CANARY: the brick SOURCE contains NO domain/manifest
     LITERAL branch (e.g. ``domain_id == "security"``). The single
     data-driven read-path loop ``m.domain_id == domain_id`` (variable vs
     variable, not a literal) is the ONLY equality and is explicitly
     allowed — that loop IS the branch-free total read path.
  #4 N2 CONTRACT TEST: ``AgentConfig`` REJECTS any manifest/domain key —
     the persona contract stays manifest-agnostic, there is no reverse link.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

import factory.domain
from factory.agent.runtime.registry_contracts import AgentConfig
from factory.domain.runtime.models import PresentationManifest

_SRC = Path(factory.domain.__file__).parent
_BEHAVIOUR_FIELDS = {"system_prompt", "tools", "skills", "model", "agent_id"}


# ── #2a SRP: manifest carries no behaviour fields ────────────────────
def test_manifest_has_no_behaviour_fields() -> None:
    assert set(PresentationManifest.model_fields) & _BEHAVIOUR_FIELDS == set()


# ── #2b SRP: runtime package is transport-free ───────────────────────
def test_runtime_imports_no_fastmcp() -> None:
    runtime_dir = _SRC / "runtime"
    modules = list(runtime_dir.rglob("*.py"))
    assert modules, "runtime package should contain modules"
    offenders = []
    for mod in modules:
        text = mod.read_text(encoding="utf-8")
        if re.search(r"^\s*(import\s+fastmcp|from\s+fastmcp)", text, re.M):
            offenders.append(str(mod.relative_to(_SRC)))
    assert offenders == [], f"runtime must not import fastmcp: {offenders}"


# ── #3 anti-branch: no domain/manifest literal branch in SOURCE ──────
def test_no_domain_literal_branch_in_source() -> None:
    # Literal-comparison patterns that would indicate a hardcoded domain
    # branch. The data-driven ``m.domain_id == domain_id`` loop compares a
    # variable to a variable (no quote follows ``==``) and is NOT matched.
    literal_patterns = [
        re.compile(r"domain_id\s*==\s*['\"]"),
        re.compile(r"manifest\s*==\s*['\"]"),
        re.compile(r"==\s*['\"]security['\"]"),
    ]
    offenders: list[str] = []
    for src in _SRC.rglob("*.py"):
        if "/test/" in src.as_posix() or "__pycache__" in src.as_posix():
            continue
        text = src.read_text(encoding="utf-8")
        for ln, line in enumerate(text.splitlines(), 1):
            stripped = line.split("#", 1)[0]  # ignore comments
            for pat in literal_patterns:
                if pat.search(stripped):
                    offenders.append(f"{src.relative_to(_SRC)}:{ln}: {line.strip()}")
    assert offenders == [], f"literal domain branch found: {offenders}"


def test_only_data_driven_equality_in_read_path() -> None:
    """Pin that the ONLY ``domain_id ==`` is the variable-vs-variable loop."""
    hits: list[str] = []
    for src in _SRC.rglob("*.py"):
        if "/test/" in src.as_posix() or "__pycache__" in src.as_posix():
            continue
        for ln, line in enumerate(src.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            if re.search(r"domain_id\s*==", code):
                hits.append(line.strip())
    # Exactly one equality, and it compares two identifiers (no literal).
    assert hits == ["if m.domain_id == domain_id:"], hits


# ── #4 N2: AgentConfig rejects any manifest/domain key ───────────────
@pytest.mark.parametrize("key", ["manifest_id", "manifest", "domain_id", "domain"])
def test_agent_config_rejects_manifest_key(key: str) -> None:
    base = dict(id="a", name="A", model="m", system_prompt="sp")
    with pytest.raises(ValidationError):
        AgentConfig(**base, **{key: "security"})


def test_agent_config_valid_without_manifest_key() -> None:
    """Sanity: the base kwargs are valid — rejection is the extra key only."""
    cfg = AgentConfig(id="a", name="A", model="m", system_prompt="sp")
    assert cfg.id == "a"
    assert "manifest_id" not in AgentConfig.model_fields
