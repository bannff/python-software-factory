from __future__ import annotations

import pytest
pytest.importorskip("langchain")
pytest.importorskip("langgraph")
pytest.importorskip("langchain_community")

from factory.agent.runtime.execution_manifest.prepare import (
    REGISTERED_GRAPH_IDS, prepare_registered_execution_manifest,
)

CONTEXT = {
    "run_id": "r", "target_app": "app", "vuln_class": "idor",
    "target_packages": ["p"], "sast_workspace": "/tmp", "target_url": "http://x",
    "sandbox_env_id": "e", "sast_run_id": "s", "agent_id": "agent",
    "metric_prefix": "m", "eval_task_description": "e", "eval_evaluators": ["x"],
    "eval_rubric": "r", "dataset_ref": "d", "objective": "o",
    "output_format": "json", "account_id": "1", "region": "us-east-1",
}

NODES = {
    "rt-scan-idor": "gptoss-idor:a|sonnet-idor:a|glm5-idor:a",
    "sandbox-setup": "resource-creator:a|mock-applier:a|sandbox-validator:a|sandbox-summary:a|eval-scorer:a",
    "eval-rl-feedback": "review:s|learn:s",
    "rt-sast-scan": "gptoss-sast:a|sonnet-sast:a|glm5-sast:a|hierarchy-analyzer:a|consolidator:a|validator:a",
    "sast": "gptoss-sast:a|sonnet-sast:a|glm5-sast:a|hierarchy-analyzer:a|consolidator:a|validator:a",
    "dast": "gptoss-dast:a|sonnet-dast:a|glm5-dast:a",
    "rt-sast-scan-hybrid": "scan-team-a:s|scan-team-b:s|scan-team-c:s|consolidator:a|validator:a",
    "rt-scan-idor-hybrid": "idor-team-a:s|idor-team-b:s|idor-team-c:s|prover:a",
    "rt-sandbox-setup-graph": "resource-creator:a|mock-applier:a|validator:a|summary:a",
    "rt-sandbox-setup-hybrid": "sandbox-team-a:s|sandbox-team-b:s|summary:a",
    "rt-sast-sonnet": "sonnet-scanner:a|sonnet-validator:a",
    "rt-sast-haiku": "haiku-scanner:a|haiku-validator:a",
    "rt-sast-nova2": "nova2-scanner:a|nova2-validator:a",
    "can-pipeline": "ingest:a|profile:a|synthesize:a|window:a|augment:a|train:a",
    "dataset-research": "planner:a|requirements:a|sources:a|quality:a|provenance:a|drafter:a",
    "review-qa": "review:a", "review-meta": "review:a",
}
ENTRIES = {
    "rt-scan-idor": "gptoss-idor|sonnet-idor|glm5-idor",
    "sandbox-setup": "resource-creator",
    "eval-rl-feedback": "review", "rt-sast-scan": "gptoss-sast|sonnet-sast|glm5-sast",
    "sast": "gptoss-sast|sonnet-sast|glm5-sast", "dast": "gptoss-dast|sonnet-dast|glm5-dast",
    "rt-sast-scan-hybrid": "scan-team-a|scan-team-b|scan-team-c",
    "rt-scan-idor-hybrid": "idor-team-a|idor-team-b|idor-team-c",
    "rt-sandbox-setup-graph": "resource-creator|mock-applier|validator",
    "rt-sandbox-setup-hybrid": "sandbox-team-a|sandbox-team-b",
    "rt-sast-sonnet": "sonnet-scanner", "rt-sast-haiku": "haiku-scanner",
    "rt-sast-nova2": "nova2-scanner", "can-pipeline": "ingest", "dataset-research": "planner",
    "review-qa": "review", "review-meta": "review",
}
EDGES = {
    "rt-scan-idor": "", "dast": "",
    "sandbox-setup": "resource-creator>mock-applier:-:resource-creator|mock-applier>sandbox-validator:-:mock-applier|sandbox-validator>sandbox-summary:-:sandbox-validator|sandbox-summary>eval-scorer:-:sandbox-summary",
    "eval-rl-feedback": "review>learn:-:review",
    "rt-sast-scan": "gptoss-sast>hierarchy-analyzer:all-predecessors-valid:gptoss-sast+sonnet-sast+glm5-sast|sonnet-sast>hierarchy-analyzer:all-predecessors-valid:gptoss-sast+sonnet-sast+glm5-sast|glm5-sast>hierarchy-analyzer:all-predecessors-valid:gptoss-sast+sonnet-sast+glm5-sast|hierarchy-analyzer>consolidator:-:hierarchy-analyzer|consolidator>validator:-:consolidator",
    "sast": "gptoss-sast>hierarchy-analyzer:all-predecessors-valid:gptoss-sast+sonnet-sast+glm5-sast|sonnet-sast>hierarchy-analyzer:all-predecessors-valid:gptoss-sast+sonnet-sast+glm5-sast|glm5-sast>hierarchy-analyzer:all-predecessors-valid:gptoss-sast+sonnet-sast+glm5-sast|hierarchy-analyzer>consolidator:-:hierarchy-analyzer|consolidator>validator:-:consolidator",
    "rt-sast-scan-hybrid": "scan-team-a>consolidator:all-predecessors-valid:scan-team-a+scan-team-b+scan-team-c|scan-team-b>consolidator:all-predecessors-valid:scan-team-a+scan-team-b+scan-team-c|scan-team-c>consolidator:all-predecessors-valid:scan-team-a+scan-team-b+scan-team-c|consolidator>validator:-:consolidator",
    "rt-scan-idor-hybrid": "idor-team-a>prover:all-predecessors-valid:idor-team-a+idor-team-b+idor-team-c|idor-team-b>prover:all-predecessors-valid:idor-team-a+idor-team-b+idor-team-c|idor-team-c>prover:all-predecessors-valid:idor-team-a+idor-team-b+idor-team-c",
    "rt-sandbox-setup-graph": "resource-creator>summary:all-predecessors-valid:resource-creator+mock-applier+validator|mock-applier>summary:all-predecessors-valid:resource-creator+mock-applier+validator|validator>summary:all-predecessors-valid:resource-creator+mock-applier+validator",
    "rt-sandbox-setup-hybrid": "sandbox-team-a>summary:all-predecessors-valid:sandbox-team-a+sandbox-team-b|sandbox-team-b>summary:all-predecessors-valid:sandbox-team-a+sandbox-team-b",
    "rt-sast-sonnet": "sonnet-scanner>sonnet-validator:-:sonnet-scanner", "rt-sast-haiku": "haiku-scanner>haiku-validator:-:haiku-scanner", "rt-sast-nova2": "nova2-scanner>nova2-validator:-:nova2-scanner",
    "can-pipeline": "ingest>profile:-:ingest|profile>synthesize:-:profile|synthesize>window:-:synthesize|window>augment:-:window|augment>train:-:augment",
    "dataset-research": "planner>requirements:-:planner|planner>sources:-:planner|planner>quality:-:planner|planner>provenance:-:planner|requirements>drafter:all-predecessors-valid:requirements+sources+quality+provenance|sources>drafter:all-predecessors-valid:requirements+sources+quality+provenance|quality>drafter:all-predecessors-valid:requirements+sources+quality+provenance|provenance>drafter:all-predecessors-valid:requirements+sources+quality+provenance",
    "review-qa": "", "review-meta": "",
}
SWARMS = {
    "eval-rl-feedback": "review=game-master+eval-judge+review-scout+review-maverick+review-nova+score-calibrator@game-master@20,40,900.0,300.0,8,3|learn=learning-synthesizer+memory-curator+learn-scout+learn-maverick+learn-haiku+reward-issuer@learning-synthesizer@20,40,900.0,300.0,8,3",
    "rt-sast-scan-hybrid": "scan-team-a=scanner-a+reviewer-a@scanner-a@4,15,900.0,300.0,8,3|scan-team-b=scanner-b+reviewer-b@scanner-b@4,15,900.0,300.0,8,3|scan-team-c=scanner-c+reviewer-c@scanner-c@4,15,900.0,300.0,8,3",
    "rt-scan-idor-hybrid": "idor-team-a=tester-a+verifier-a@tester-a@4,25,900.0,300.0,8,3|idor-team-b=tester-b+verifier-b@tester-b@4,25,900.0,300.0,8,3|idor-team-c=tester-c+verifier-c@tester-c@4,25,900.0,300.0,8,3",
    "rt-sandbox-setup-hybrid": "sandbox-team-a=creator-a+checker-a@creator-a@4,15,900.0,300.0,8,3|sandbox-team-b=creator-b+checker-b@creator-b@4,15,900.0,300.0,8,3",
}
LIMITS = {"rt-scan-idor": "10,900.0,300.0", "sandbox-setup": "25,3600.0,1800.0", "eval-rl-feedback": "25,1800.0,300.0", "rt-sast-scan": "30,5400.0,1800.0", "sast": "30,5400.0,1800.0", "dast": "25,900.0,300.0", "rt-sast-scan-hybrid": "3,5400.0,1800.0", "rt-scan-idor-hybrid": "10,900.0,300.0", "rt-sandbox-setup-graph": "3,1800.0,600.0", "rt-sandbox-setup-hybrid": "3,1800.0,600.0", "rt-sast-sonnet": "1,2400.0,900.0", "rt-sast-haiku": "1,2400.0,900.0", "rt-sast-nova2": "1,2400.0,900.0", "can-pipeline": "30,3600.0,1200.0", "dataset-research": "6,1800.0,300.0", "review-qa": "1,300.0,240.0", "review-meta": "1,300.0,240.0"}


def _edge(edge):
    condition = edge.condition.kind if edge.condition else "-"
    return f"{edge.source}>{edge.target}:{condition}:{'+'.join(edge.predecessors)}"


def _swarm(node):
    limits = ",".join(str(value) for value in node.limits.model_dump().values())
    return f"{node.id}={'+'.join(member.id for member in node.members)}@{node.entry_point}@{limits}"


def test_exact_registered_manifest_matrix_snapshot() -> None:
    assert tuple(NODES) == REGISTERED_GRAPH_IDS
    for graph_id in REGISTERED_GRAPH_IDS:
        manifest = prepare_registered_execution_manifest(graph_id, "task", CONTEXT)
        assert "|".join(f"{node.id}:{node.type[0]}" for node in manifest.nodes) == NODES[graph_id]
        assert "|".join(manifest.entry_points) == ENTRIES[graph_id]
        assert "|".join(_edge(edge) for edge in manifest.edges) == EDGES[graph_id]
        assert "|".join(_swarm(node) for node in manifest.nodes if node.type == "swarm") == SWARMS.get(graph_id, "")
        assert ",".join(str(value) for value in manifest.limits.model_dump().values()) == LIMITS[graph_id]
