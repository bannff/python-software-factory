"""Property tests for registry_contracts.py (bd python-factory-uffq).

8 Hypothesis properties at max_examples=80 each: P1 round-trip per
kind, P2 discriminator routes via ``kind``, P3 ``extra="forbid"``
rejects fuzz, P4 missing required field raises, P5 NodeRef sub-
discriminator routes by ``type``, P6 ``WorkflowConfig.factory``
cross-checks ``FACTORY_REGISTRY``, P7 every default validates,
P8 ``model_json_schema`` is stable.
"""
from __future__ import annotations

import string

from hypothesis import given, settings, strategies as st
from pydantic import TypeAdapter, ValidationError
import pytest

from factory.agent.registry.factories import known_factories
from factory.agent.runtime.registry_contracts import (
    GraphConfig, NodeRef, RegistryConfig,
    SwarmAgentConfig, SwarmConfig, WorkflowConfig,
)

_NODE_ADAPTER: TypeAdapter[NodeRef] = TypeAdapter(NodeRef)
_REG_ADAPTER: TypeAdapter[RegistryConfig] = TypeAdapter(RegistryConfig)

_id_alphabet = string.ascii_lowercase + string.digits + "-_"
_ids = st.text(alphabet=_id_alphabet, min_size=1, max_size=20).filter(
    lambda s: s and not s.isspace()
)
_models = st.sampled_from([
    "us.anthropic.claude-sonnet-4-6",
    "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "openai.gpt-oss-120b-1:0",
])
_known_factory = st.sampled_from(list(known_factories()))


# --- P1: round-trip per kind ---

@settings(max_examples=80, deadline=None)
@given(gid=_ids, name=_ids)
def test_p1_roundtrip_graph(gid: str, name: str) -> None:
    g = GraphConfig(id=gid, name=name)
    assert g == GraphConfig.model_validate(g.model_dump(by_alias=True))


@settings(max_examples=80, deadline=None)
@given(wid=_ids, name=_ids, fkey=_known_factory)
def test_p1_roundtrip_workflow(wid: str, name: str, fkey: str) -> None:
    w = WorkflowConfig(id=wid, kind="workflow", factory=fkey, name=name)
    assert w == WorkflowConfig.model_validate(w.model_dump(by_alias=True))


@settings(max_examples=80, deadline=None)
@given(sid=_ids, name=_ids, ep=_ids, model=_models)
def test_p1_roundtrip_swarm(sid: str, name: str, ep: str, model: str) -> None:
    sw = SwarmConfig(
        id=sid, name=name, entry_point=ep,
        agents=[SwarmAgentConfig(id=ep, model=model, system_prompt="hi")],
    )
    assert sw == SwarmConfig.model_validate(sw.model_dump(by_alias=True))


# --- P2: discriminator routes correctly ---

@settings(max_examples=80, deadline=None)
@given(
    kind=st.sampled_from(["graph", "workflow", "swarm"]),
    rid=_ids, name=_ids, ep=_ids, fkey=_known_factory,
)
def test_p2_discriminator_routes(
    kind: str, rid: str, name: str, ep: str, fkey: str,
) -> None:
    if kind == "graph":
        cfg = _REG_ADAPTER.validate_python(
            {"id": rid, "kind": "graph", "name": name})
        assert isinstance(cfg, GraphConfig)
    elif kind == "workflow":
        cfg = _REG_ADAPTER.validate_python(
            {"id": rid, "kind": "workflow",
             "factory": fkey, "name": name})
        assert isinstance(cfg, WorkflowConfig)
    else:
        cfg = _REG_ADAPTER.validate_python(
            {"id": rid, "kind": "swarm",
             "name": name, "entry_point": ep})
        assert isinstance(cfg, SwarmConfig)
    assert cfg.kind == kind


# --- P3: extra="forbid" rejects fuzzed unknown keys ---

_NEVER = (
    set(GraphConfig.model_fields) | set(WorkflowConfig.model_fields)
    | set(SwarmConfig.model_fields) | {"class"}
)
_unknown = st.text(
    alphabet=string.ascii_lowercase + "_", min_size=4, max_size=15,
).filter(lambda s: s not in _NEVER)

@settings(max_examples=80, deadline=None)
@given(unknown=_unknown, gid=_ids, name=_ids)
def test_p3_extra_forbid_graph(unknown: str, gid: str, name: str) -> None:
    with pytest.raises(ValidationError):
        GraphConfig.model_validate({"id": gid, "name": name, unknown: "x"})


# --- P4: missing required field raises ---

@settings(max_examples=80, deadline=None)
@given(name=_ids)
def test_p4_missing_id_graph(name: str) -> None:
    with pytest.raises(ValidationError):
        GraphConfig.model_validate({"name": name})


@settings(max_examples=80, deadline=None)
@given(wid=_ids, name=_ids, fkey=_known_factory)
def test_p4_missing_workflow_kind(wid: str, name: str, fkey: str) -> None:
    """WorkflowConfig.kind has no default — omitting it must fail."""
    with pytest.raises(ValidationError):
        WorkflowConfig.model_validate({
            "id": wid, "factory": fkey, "name": name,
        })


# --- P5: NodeRef sub-discriminator routes by `type` ---

@settings(max_examples=80, deadline=None)
@given(
    nid=_ids, swid=_ids, gid=_ids, model=_models,
    ntype=st.sampled_from(["agent", "swarm", "graph"]),
)
def test_p5_node_subdiscriminator(
    nid: str, swid: str, gid: str, model: str, ntype: str,
) -> None:
    if ntype == "agent":
        n = _NODE_ADAPTER.validate_python(
            {"id": nid, "type": "agent", "model": model})
    elif ntype == "swarm":
        n = _NODE_ADAPTER.validate_python(
            {"id": nid, "type": "swarm", "swarm_id": swid})
    else:
        n = _NODE_ADAPTER.validate_python(
            {"id": nid, "type": "graph", "graph_id": gid})
    assert n.type == ntype

# --- P6: WorkflowConfig.factory cross-checks registry ---

@settings(max_examples=80, deadline=None)
@given(
    bogus=st.text(
        alphabet=string.ascii_lowercase + "_", min_size=3, max_size=20,
    ).filter(lambda s: s not in known_factories() and s),
    wid=_ids, name=_ids,
)
def test_p6_factory_typo_rejected(
    bogus: str, wid: str, name: str,
) -> None:
    with pytest.raises(ValidationError):
        WorkflowConfig(id=wid, kind="workflow", factory=bogus, name=name)


def test_p6_known_factory_passes() -> None:
    for fkey in known_factories():
        w = WorkflowConfig(id="t", kind="workflow", factory=fkey, name="n")
        assert w.factory == fkey

# --- P7: every default validates as expected kind ---

def test_p7_defaults_typed_kinds() -> None:
    from factory.agent.registry.defaults import (
        AGENTS_TYPED, GRAPHS_TYPED, SWARMS_TYPED,
    )
    assert all(g.kind in {"graph", "workflow"} for g in GRAPHS_TYPED)
    assert all(s.kind == "swarm" for s in SWARMS_TYPED)
    # bd:python-factory-hadbi.1 — every AgentConfig has skills list.
    assert all(isinstance(a.skills, list) for a in AGENTS_TYPED)


def test_p7_workflow_canary_shape() -> None:
    """rt-sast-scan dumps to the same shape it would as a dict."""
    from factory.agent.registry.defaults_code_scan import (
        SAST_TARGETED_REGISTRATION,
    )
    d = SAST_TARGETED_REGISTRATION.model_dump(by_alias=True)
    assert d["id"] == "rt-sast-scan"
    assert d["kind"] == "workflow"
    assert d["factory"] == "sast_targeted"
    assert d["execution_timeout"] == 5400
    assert d["node_timeout"] == 1800
    assert "vuln_class" in d["context_vars"]


# --- P8: schema is stable across calls ---

@pytest.mark.parametrize("model", [GraphConfig, WorkflowConfig, SwarmConfig])
def test_p8_schema_stable(model: type) -> None:
    assert model.model_json_schema() == model.model_json_schema()
