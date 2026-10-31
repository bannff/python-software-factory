"""SOP report builder — Phase 4 of the Eval SOP workflow.

Generates a structured evaluation report from SOP session state.
Separated from sop_adapter.py to respect <200 LOC per file.
"""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .sop_adapter import SOPState


def build_report(state: "SOPState") -> str:
    """Build a structured evaluation report from SOP state.

    Follows the Eval SOP report format:
    - Executive summary with overall score
    - Per-case results with pass/fail
    - Evaluation plan reference
    - Recommendations

    Args:
        state: Completed SOP session state.

    Returns:
        Markdown-formatted evaluation report.
    """
    results = state.eval_results
    summary = results.get("summary", {})
    case_results = results.get("case_results", [])
    evaluators = results.get("evaluators", [])

    lines = [
        f"# Evaluation Report — SOP Session {state.id}",
        "",
        "## Executive Summary",
        "",
        f"- **Overall Score**: {summary.get('overall_score', 'N/A')}",
        f"- **Pass Rate**: {_fmt_rate(summary.get('pass_rate'))}",
        f"- **Total Cases**: {summary.get('total_cases', len(case_results))}",
        f"- **Evaluators**: {', '.join(evaluators)}",
        "",
        "## Case Results",
        "",
    ]

    for cr in case_results:
        icon = "✅" if cr.get("passed") else "❌"
        score = cr.get("score", 0)
        name = cr.get("case_name", "?")
        reason = cr.get("reason", "")
        lines.append(f"- {icon} **{name}**: {score:.2f} — {reason}")

    lines.extend([
        "",
        "## Evaluation Plan",
        "",
        f"- **Agent**: {state.agent_description[:120]}",
        f"- **Goals**: {state.evaluation_goals or 'General assessment'}",
        f"- **Recommended Evaluators**: "
        f"{state.eval_plan.get('recommended_evaluators', [])}",
        "",
        "## Recommendations",
        "",
    ])

    # Generate recommendations based on results
    lines.extend(_generate_recommendations(summary, case_results))

    return "\n".join(lines)


def _fmt_rate(rate: Any) -> str:
    """Format a pass rate for display."""
    if rate is None:
        return "N/A"
    if isinstance(rate, (int, float)):
        return f"{rate:.0%}" if rate <= 1.0 else str(rate)
    return str(rate)


def _generate_recommendations(
    summary: dict[str, Any],
    case_results: list[dict[str, Any]],
) -> list[str]:
    """Generate recommendations based on evaluation results."""
    lines = []
    pass_rate = summary.get("pass_rate", 0)
    overall = summary.get("overall_score", 0)

    if pass_rate < 0.75:
        lines.append(
            "- ⚠️ Pass rate below 75% threshold — "
            "review failing cases for systematic issues"
        )
    if overall and overall < 0.7:
        lines.append(
            "- ⚠️ Overall score below 0.7 — "
            "consider improving agent prompt or capabilities"
        )

    failures = [cr for cr in case_results if not cr.get("passed")]
    if failures:
        lines.append(
            f"- 🔍 {len(failures)} case(s) failed — "
            "review reasons and adjust test cases or agent behavior"
        )

    if not lines:
        lines.append("- ✅ All criteria met — agent performing well")

    return lines
