"""MCP Prompt registration for Evals brick.

Prompts provide guided workflows for common tasks:
- Creating evaluation suites
- Running evaluations
- Analyzing results
- Comparing runs
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from typing import Any

from .templates import PROMPT_TEMPLATES

if TYPE_CHECKING:
    from ..runtime.runtime import EvalsRuntime


def register(
    mcp: Any,
    get_runtime: Callable[[], "EvalsRuntime"],
) -> None:
    """Register all Evals prompts with the MCP server."""

    @mcp.prompt()
    def create_eval(
        name: str,
        purpose: str = "",
    ) -> str:
        """Generate guidance for creating an evaluation suite."""
        suite_id = name.lower().replace(" ", "-").replace("_", "-")
        
        return PROMPT_TEMPLATES["create_eval"]["template"].format(
            name=name,
            suite_id=suite_id,
            purpose=purpose or f"Evaluate agent performance on {name}",
        )

    @mcp.prompt()
    def run_eval(
        suite_id: str,
        backend: str = "custom",
    ) -> str:
        """Generate guidance for running evaluations."""
        return PROMPT_TEMPLATES["run_eval"]["template"].format(
            suite_id=suite_id,
            backend=backend,
        )

    @mcp.prompt()
    def analyze_results(run_id: str) -> str:
        """Generate guidance for analyzing evaluation results."""
        return PROMPT_TEMPLATES["analyze_results"]["template"].format(
            run_id=run_id,
        )

    @mcp.prompt()
    def compare_runs(
        run_a: str,
        run_b: str,
    ) -> str:
        """Generate guidance for comparing evaluation runs."""
        return PROMPT_TEMPLATES["compare_runs"]["template"].format(
            run_a=run_a,
            run_b=run_b,
        )

    @mcp.prompt()
    def evaluate_output(
        evaluator: str = "output",
        rubric: str = "",
    ) -> str:
        """Generate guidance for evaluating pre-existing output."""
        return (
            f"# Evaluate Output with {evaluator}\n\n"
            "## Direct Evaluation (No Agent Needed)\n\n"
            "Use `evals_evaluate` to run a Strands evaluator directly:\n\n"
            "```\n"
            "evals_evaluate(\n"
            '    input_text="Your original prompt/query",\n'
            '    output_text="The LLM output to evaluate",\n'
            f'    evaluator_name="{evaluator}",\n'
            f'    rubric="{rubric or "Score 1.0 if accurate and complete..."}"\n'
            ")\n"
            "```\n\n"
            "## Multi-Evaluator Batch\n\n"
            "```\n"
            "evals_evaluate_multi(\n"
            '    input_text="...",\n'
            '    output_text="...",\n'
            '    evaluator_names=["output", "helpfulness", "faithfulness"],\n'
            '    rubric="..."\n'
            ")\n"
            "```\n\n"
            "## Available Evaluators\n\n"
            "Run `evals_list_evaluators()` to see all 12 built-in evaluators.\n"
        )

    @mcp.prompt()
    def eval_sop(
        agent_description: str = "",
    ) -> str:
        """Generate guidance for running the Eval SOP workflow."""
        return (
            "# Eval SOP \u2014 4-Phase Evaluation Workflow\n\n"
            "## Phase 1: Plan\n"
            "```\n"
            "evals_sop_plan(\n"
            f'    agent_description="{agent_description or "Your agent description"}",'  "\n"
            '    agent_tools=["tool1", "tool2"],\n'
            '    evaluation_goals="accuracy and helpfulness"\n'
            ")\n"
            "```\n\n"
            "## Phase 2: Generate Test Data\n"
            "```\n"
            'evals_sop_generate_data(session_id="<from phase 1>", num_cases=10)\n'
            "```\n\n"
            "## Phase 3: Run Evaluation\n"
            "```\n"
            'evals_sop_run(session_id="<same>", model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0")\n'
            "```\n\n"
            "## Phase 4: Generate Report\n"
            "```\n"
            'evals_sop_report(session_id="<same>")\n'
            "```\n"
        )
