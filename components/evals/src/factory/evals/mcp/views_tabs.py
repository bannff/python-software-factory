"""Tab and action builders for Evals dashboard views.

Exports: evals_read_tabs, evals_actions, suites_read_tabs, suites_actions.
Split from views.py to stay under 200 LOC per file.
"""

from __future__ import annotations

from typing import Any



def evals_read_tabs() -> dict[str, Any]:
    """Tabs component for read-only evals data."""
    return {
        "id": "evals-read-tabs",
        "type": "tabs",
        "props": {
            "active": "experiments",
            "tabs": [
                {"id": "experiments", "label": "Experiments",
                 "lazy_tool": "evals_list_saved_experiments"},
                {"id": "runs", "label": "Runs",
                 "lazy_tool": "evals_list_runs"},
                {"id": "evaluators", "label": "Evaluators",
                 "lazy_tool": "evals_list_evaluators"},
                {"id": "simulations", "label": "Simulations",
                 "lazy_tool": "evals_list_ui_scenarios"},
                {"id": "sop", "label": "SOP Sessions",
                 "lazy_tool": "evals_sop_list"},
            ],
        },
    }


def evals_actions() -> list[dict[str, Any]]:
    """Return action definitions for the evals action pane."""
    return [_run_experiment(), _evaluate(), _sop_plan()]


def _run_experiment() -> dict[str, Any]:
    return {
        "id": "run-experiment", "label": "Run Experiment", "icon": "▶️",
        "tool": "evals_run_experiment",
        "submit_label": "Run",
        "fields": [
            {"name": "cases", "label": "Cases (JSON array)",
             "type": "textarea",
             "placeholder": '[{"name": "case-1", "input": {"prompt": "..."}}]',
             "tooltip": "JSON array of test cases — each needs name and input"},
            {"name": "evaluator_names", "label": "Evaluators (comma-sep)",
             "type": "text", "placeholder": "output, helpfulness",
             "tooltip": "Comma-separated evaluator names to score against"},
            {"name": "model_id", "label": "Model ID", "type": "text",
             "placeholder": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
             "tooltip": "Bedrock model ID for the agent under test"},
            {"name": "system_prompt", "label": "System Prompt",
             "type": "textarea",
             "placeholder": "You are a helpful assistant.",
             "tooltip": "System prompt for the agent under test"},
        ],
    }


def _evaluate() -> dict[str, Any]:
    return {
        "id": "evaluate", "label": "Quick Evaluate", "icon": "⚖️",
        "tool": "evals_evaluate",
        "submit_label": "Evaluate",
        "fields": [
            {"name": "input_text", "label": "Input", "type": "textarea",
             "placeholder": "Original prompt or query",
             "tooltip": "The input that was given to the LLM"},
            {"name": "output_text", "label": "Output", "type": "textarea",
             "placeholder": "LLM response to evaluate",
             "tooltip": "The output to score"},
            {"name": "evaluator_name", "label": "Evaluator",
             "type": "select",
             "options": [
                 {"value": "output", "label": "Output Quality"},
                 {"value": "helpfulness", "label": "Helpfulness"},
                 {"value": "faithfulness", "label": "Faithfulness"},
                 {"value": "coherence", "label": "Coherence"},
                 {"value": "conciseness", "label": "Conciseness"},
                 {"value": "harmfulness", "label": "Harmfulness"},
                 {"value": "response_relevance", "label": "Relevance"},
             ],
             "tooltip": "Strands LLMAJ evaluator to use"},
            {"name": "rubric", "label": "Rubric", "type": "text",
             "placeholder": "Custom scoring rubric (optional)",
             "tooltip": "Required for output/trajectory evaluators"},
        ],
    }


def _sop_plan() -> dict[str, Any]:
    return {
        "id": "sop-plan", "label": "SOP: Plan Evaluation", "icon": "🗺️",
        "tool": "evals_sop_plan",
        "submit_label": "Create Plan",
        "fields": [
            {"name": "agent_description", "label": "Agent Description",
             "type": "textarea",
             "placeholder": "Describe the agent's purpose and capabilities...",
             "tooltip": "Phase 1 — analyzes agent and recommends evaluators"},
            {"name": "evaluation_goals", "label": "Evaluation Goals",
             "type": "text",
             "placeholder": "multi-turn accuracy, safety, tool usage",
             "tooltip": "What aspects to evaluate"},
        ],
    }


def suites_read_tabs() -> dict[str, Any]:
    """Tabs component for read-only suites data."""
    return {
        "id": "suites-read-tabs",
        "type": "tabs",
        "props": {
            "active": "all-suites",
            "tabs": [
                {"id": "all-suites", "label": "All Suites",
                 "lazy_tool": "evals_list_suites"},
                {"id": "suite-runs", "label": "Runs",
                 "lazy_tool": "evals_list_runs"},
                {"id": "health", "label": "Health",
                 "lazy_tool": "evals_health_check"},
            ],
        },
    }


def suites_actions() -> list[dict[str, Any]]:
    """Return action definitions for the suites action pane."""
    return [_add_case(), _lookup_suite(), _delete_suite()]


def _add_case() -> dict[str, Any]:
    return {
        "id": "add-case", "label": "Add Test Case", "icon": "➕",
        "tool": "evals_add_case",
        "submit_label": "Add Case",
        "fields": [
            {"name": "suite_id", "label": "Suite ID", "type": "text",
             "placeholder": "Target suite ID",
             "tooltip": "ID of the suite to add this case to"},
            {"name": "case_id", "label": "Case ID", "type": "text",
             "placeholder": "unique-case-id",
             "tooltip": "Unique identifier for this test case"},
            {"name": "name", "label": "Case Name", "type": "text",
             "placeholder": "Descriptive case name",
             "tooltip": "Human-readable name for the test case"},
            {"name": "input_data", "label": "Input Data (JSON)",
             "type": "textarea",
             "placeholder": '{"prompt": "Test input"}',
             "tooltip": "JSON object with the test input data"},
        ],
    }


def _lookup_suite() -> dict[str, Any]:
    return {
        "id": "lookup-suite", "label": "Lookup Suite", "icon": "🔍",
        "tool": "evals_get_suite",
        "submit_label": "Lookup",
        "fields": [
            {"name": "suite_id", "label": "Suite ID", "type": "text",
             "placeholder": "Suite ID to look up",
             "tooltip": "Returns suite details including case count"},
        ],
    }


def _delete_suite() -> dict[str, Any]:
    return {
        "id": "delete-suite", "label": "⚠ Delete Suite", "icon": "🗑️",
        "tool": "evals_delete_suite",
        "submit_label": "Delete",
        "fields": [
            {"name": "suite_id", "label": "Suite ID", "type": "text",
             "placeholder": "Suite ID to delete",
             "tooltip": "Permanently removes the suite and its cases"},
        ],
    }
