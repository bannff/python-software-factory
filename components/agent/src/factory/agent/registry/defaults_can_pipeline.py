"""CAN bus failure prediction pipeline graph (Epic 6 — Agentic Dataset Skills).

5-stage data pipeline reflected as a 6-node agent graph:
``can-ingest → can-profiler → can-synthesizer → can-trainer``. The
five dataset stages — ``ingest → profile → synthesize → window →
augment`` — are orchestrated by the recipe materializer (see
``factory.dataset.runtime.materializer``); the ``window`` and
``augment`` graph nodes are documentation markers that share the
``can-synthesizer`` agent persona because all five dataset stages are
submitted as a single ``recipe://local/can-pipeline-aug@1`` job.
The ``train`` node is an ML step (``ml_train_timeseries``), not a
dataset stage, but is kept in the graph for end-to-end visibility.

Each ``agent``-type node references a registered ``AgentConfig``;
runtime ``system_prompt`` and ``skills`` resolve from the registry at
graph build time (AgentNodeRef.agent_id → defaults.AGENTS_TYPED
lookup). The graph itself is the registered ``can-pipeline``; agent
personas live in ``defaults_can_agents`` and skill content in
``skills/{can-analyst,can-recipe-author,can-evaluator}/SKILL.md``.

bd:python-factory-2tgo1 — the per-node ``skills`` field is left empty
because each node's system_prompt is owned by the referenced agent
(no inline override ⇒ no need to duplicate the skills list here).
"""
from __future__ import annotations

from ..runtime.registry_contracts import GraphConfig

CAN_PIPELINE_GRAPH: dict = {
    "id": "can-pipeline",
    "name": "CAN Analysis Pipeline",
    "description": (
        "6-node graph reflecting the 5-stage CAN data pipeline "
        "(ingest → profile → synthesize → window → augment) plus the "
        "post-pipeline ML train step. The window/augment nodes share "
        "the can-synthesizer agent persona because the recipe "
        "materializer executes all five dataset stages in a single "
        "recipe submission. Each agent owns its own skill set "
        "(can-analyst, can-recipe-author, can-evaluator)."
    ),
    "required_bricks": [
        "dataset", "machine_learning", "evals", "memory", "llm_gateway",
    ],
    "context_vars": ["run_id", "target_app", "trace_id"],
    "entry_points": ["ingest"],
    "nodes": [
        {"id": "ingest", "type": "agent",
         "agent_id": "can-ingest",
         "description": "MF4 ingest + DBC matching (can-analyst)"},
        {"id": "profile", "type": "agent",
         "agent_id": "can-profiler",
         "description": "Signal boundary + temporal profile (can-analyst)"},
        {"id": "synthesize", "type": "agent",
         "agent_id": "can-synthesizer",
         "description": "Synthetic CAN frames + failure injection "
                        "(can-recipe-author)"},
        # Recipe-driven data transformation — executed by the recipe
        # materializer as part of can-synthesizer's single
        # ``can-pipeline-aug@1`` submission (stage: can_window).
        {"id": "window", "type": "agent",
         "agent_id": "can-synthesizer",
         "description": "Recipe-driven rolling window construction "
                        "(can-recipe-author; no new agent persona — "
                        "delegated to the recipe materializer)"},
        # Recipe-driven data transformation — executed by the recipe
        # materializer as part of can-synthesizer's single
        # ``can-pipeline-aug@1`` submission (stage: can_augment).
        {"id": "augment", "type": "agent",
         "agent_id": "can-synthesizer",
         "description": "Recipe-driven data augmentation "
                        "(can-recipe-author; no new agent persona — "
                        "delegated to the recipe materializer)"},
        # ML tool invocation, NOT a dataset stage — the recipe
        # materializer hands the resolved manifest to the trainer
        # which calls ``ml_train_timeseries``.
        {"id": "train", "type": "agent",
         "agent_id": "can-trainer",
         "description": "Time-series training + 6-metric eval "
                        "(can-evaluator) — ML tool invocation, "
                        "not a dataset stage"},
    ],
    "edges": [
        {"source": "ingest", "target": "profile"},
        {"source": "profile", "target": "synthesize"},
        {"source": "synthesize", "target": "window"},
        {"source": "window", "target": "augment"},
        {"source": "augment", "target": "train"},
    ],
    "execution_timeout": 3600.0,
    "node_timeout": 1200.0,
}

# Validate-on-build (defaults.py: GRAPHS_TYPED validates every entry).
# Mirrors the pattern in defaults_sandbox_hybrid.SANDBOX_HYBRID_GRAPH and
# defaults_dast_open.DAST_OPEN_GRAPHS — export the validated model so
# ``from .defaults_can_pipeline import CAN_PIPELINE_GRAPH_TYPED`` lands
# a fully-typed GraphConfig in the loader.
CAN_PIPELINE_GRAPH_TYPED: GraphConfig = GraphConfig.model_validate(
    CAN_PIPELINE_GRAPH
)

# Back-compat shape for callers that expect a list (mirrors
# ``SANDBOX_GRAPHS`` / ``DAST_OPEN_GRAPHS`` in defaults.py).
CAN_PIPELINE_GRAPHS: list = [CAN_PIPELINE_GRAPH]


__all__ = [
    "CAN_PIPELINE_GRAPH", "CAN_PIPELINE_GRAPH_TYPED", "CAN_PIPELINE_GRAPHS",
]
