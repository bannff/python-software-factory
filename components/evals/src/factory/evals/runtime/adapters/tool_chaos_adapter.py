"""SDK-native ToolSimulator and ChaosExperiment orchestration."""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from ..ports import EvalCase, ExperimentConfig, ExperimentReport
from ..simulation_report import build_report
from ..tool_chaos_artifacts import build_tool_chaos_artifacts
from ..tool_chaos_contract import MAX_STATE_CACHE, bounded_value
from .tool_catalog import register_catalog


def _input(case: EvalCase) -> str:
    raw = case.input
    return raw if isinstance(raw, str) else str(raw.get("query", raw.get("input", raw)))


def _expected(case: EvalCase) -> str | None:
    raw = case.expected
    if raw is None or isinstance(raw, str):
        return raw
    return str(raw.get("output", raw.get("response", raw)))


def _variants(config: ExperimentConfig, faults: list[dict[str, Any]]) -> tuple[list[Any], list[EvalCase]]:
    from strands_evals.chaos import ChaosCase
    variants, report_cases = [], []
    for case_ordinal, case in enumerate(config.cases):
        for fault_ordinal, fault in enumerate(faults):
            pair_key = f"pair-{case_ordinal}-{fault_ordinal}"
            for condition, effects in (("baseline", {}), (fault["condition"], fault["effects"])):
                identity = {"pair_key": pair_key, "condition": condition}
                variants.append(ChaosCase(
                    name=f"variant-{len(variants)}", input=_input(case), expected_output=_expected(case),
                    metadata={**case.metadata, "tool_chaos": identity}, effects=effects,
                ))
                report_cases.append(EvalCase(
                    id=f"variant-{len(report_cases)}", name=f"variant-{len(report_cases)}",
                    input=_input(case), expected=case.expected, metadata={"tool_chaos": identity},
                ))
    return variants, report_cases


def run_tool_chaos(
    config: ExperimentConfig, tool_names: tuple[str, ...], faults: list[dict[str, Any]],
) -> tuple[ExperimentReport, dict[str, Any]]:
    """Evaluate fresh baseline/fault tool simulators through native chaos APIs."""
    from strands import Agent
    from strands_evals.chaos import ChaosExperiment, ChaosPlugin
    from strands_evals.simulation.tool_simulator import StateRegistry, ToolSimulator
    from .evaluator_factory import build_evaluators
    agent_config = config.agent_config
    if agent_config and agent_config.agent_id:
        raise ValueError("agent_id targets cannot attach ChaosPlugin on the registered-persona MCP route")
    variants, report_cases = _variants(config, faults)
    evidence: list[dict[str, Any]] = []

    def task(case: Any) -> dict[str, Any]:
        identity = dict(case.metadata["tool_chaos"])
        registry = StateRegistry(max_tool_call_cache_size=MAX_STATE_CACHE)
        simulator = ToolSimulator(state_registry=registry, model=agent_config.model_id if agent_config else None)
        wrappers = register_catalog(simulator, tool_names)
        target = Agent(
            system_prompt=agent_config.system_prompt if agent_config else "You are a helpful assistant.",
            model=agent_config.model_id if agent_config else None, tools=wrappers,
            plugins=[ChaosPlugin()], callback_handler=None,
        )
        output = str(target(case.input))
        evidence.append({
            **identity, "effects": bounded_value(case.effects),
            "tool_states": [
                {"tool_name": name, "state": bounded_value(simulator.get_state(name))}
                for name in tool_names
            ],
        })
        return {"output": output}
    native = ChaosExperiment(cases=variants, evaluators=build_evaluators(config.evaluator_names, config.rubric, framework="strands"))
    native_report = native.run_evaluations(task)
    report = build_report(replace(config, cases=report_cases), native_report, evidence)
    return report, build_tool_chaos_artifacts(report, evidence)
