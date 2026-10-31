"""Import and signature canaries for the native generation stages.

The stages were ported from bannff/Agentic-Datasets@26cb683 into
``factory.dataset.runtime.stages``. This canary fails loudly when a stage
callable's parameter surface drifts from the contract the adapters and
recipes depend on.
"""

from __future__ import annotations

import importlib
import inspect

EXPECTED_STAGE_PARAMETERS = {
    "agentinstruct": {
        "records", "k_variants", "transforms", "complexity_levels", "dedupe",
        "use_llm", "completion",
    },
    "s2m": {"records", "min_turns", "max_turns", "use_llm", "completion"},
    "apigenmt": {
        "records", "tools", "max_tools_per_conversation", "use_llm",
        "generate_responses", "completion",
    },
    "reviewinstruct": {
        "records", "accept_threshold", "max_iterations", "use_llm", "completion",
    },
}

STAGE_IMPORTS = {
    "agentinstruct": "factory.dataset.runtime.stages.agentinstruct.agentinstruct",
    "s2m": "factory.dataset.runtime.stages.s2m.s2m",
    "apigenmt": "factory.dataset.runtime.stages.apigenmt.apigenmt",
    "reviewinstruct": "factory.dataset.runtime.stages.reviewinstruct.reviewinstruct",
}


def verify_stage_contract() -> None:
    """Fail when a native stage callable surface changes incompatibly."""
    for stage_name, import_path in STAGE_IMPORTS.items():
        module_name, function_name = import_path.rsplit(".", 1)
        stage = getattr(importlib.import_module(module_name), function_name)
        parameters = set(inspect.signature(stage).parameters)
        if parameters != EXPECTED_STAGE_PARAMETERS[stage_name]:
            raise RuntimeError(
                f"Unexpected {stage_name} signature: {sorted(parameters)}"
            )
