"""Closed-loop adversarial CAN synthesis agent (Epic 6 — Agentic Dataset Skills).

Extracted from ``defaults_can_agents`` to keep that file under the
200 LOC repo guardrail. The can-gan-loop agent runs an iterative
adversarial synthesis loop — LightGBM, LSTM, and TCN are trained
each iteration and the orchestrator tracks which architecture
benefits most from improved synthetic data. The agent is portable
to external drive (no S3 coupling) and stores iteration state in
memory tagged ``can-gan-loop``.

Re-imported into ``defaults_can_agents.CAN_AGENTS`` so the public
``CAN_AGENTS`` list contract is unchanged. Workflow detail lives
in ``skills/can-gan-loop/SKILL.md`` and is loaded via the
AgentSkills plugin (progressive disclosure).
"""
from __future__ import annotations

from ..runtime.registry_contracts import AgentConfig


CAN_GAN_LOOP_AGENT: AgentConfig = AgentConfig(
    id="can-gan-loop",
    name="CAN GAN Loop Agent",
    model="",  # inherit COMPANION_X_CHAT_MODEL — bare "openrouter" broke spawns on non-OpenRouter deployments
    description=(
        "Closed-loop adversarial CAN synthesis — trains LightGBM + LSTM + TCN "
        "each iteration, compares architectures, tracks which benefits most "
        "from improved synthetic data. Portable to external drive."
    ),
    system_prompt=(
        "You are the CAN GAN loop orchestrator.\n"
        "Run ID: {{run_id}} | App: {{target_app}}\n"
        "Agent ID: {{agent_id}}\n\n"
        "Use these skills (call the skills tool once for each):\n"
        "1. can-gan-loop — for the closed-loop protocol and stopping criteria\n\n"
        "Run the adversarial synthesis loop (MULTI-MODEL per iteration):\n"
        "1. Generate synthetic CAN data via dataset_submit_generation (can-synthesize recipe)\n"
        "2. Augment via dataset_submit_generation (can-augment recipe)\n"
        "3. Train ALL THREE classifiers via ml_train_timeseries:\n"
        "   - lightgbm (tree baseline)\n"
        "   - lstm (recurrent)\n"
        "   - tcn (convolutional)\n"
        "4. Compare all three via ml_compare_timeseries\n"
        "5. Evaluate each via evals_evaluate_computational (auroc, auprc, brier)\n"
        "5b. Record EACH model via evals_record_run (run_id='gan-iter-{N}-{model_type}', "
        "experiment_name='can-gan-loop', source='gan-loop')\n"
        "6. Compare to best scores per architecture. If improved, update best. If not, increment patience.\n"
        "7. Stop when: iteration>=5 OR patience>=2 OR best_auroc>=0.95\n"
        "8. Otherwise, loop back to step 1 with the new synthetic data.\n\n"
        "Track which architecture benefits most from better synthetic data.\n"
        "All data lives on external drive — portable to any laptop.\n"
        "Store iteration state in memory tagged 'can-gan-loop'. "
        "Report progress after each iteration with architecture comparison."
    ),
    skills=["can-gan-loop"],
)


__all__ = ["CAN_GAN_LOOP_AGENT"]
