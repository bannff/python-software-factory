"""Tab and action builders for Security Operations dashboard.

Exports:
- security_read_tabs(): read-only tabs component
- security_actions(): list of write-operation action dicts for action_pane

Split from views.py to stay under 200 LOC per file.
"""

from __future__ import annotations

from typing import Any



# ── Read-only tabs ─────────────────────────────────────────────────


def security_read_tabs() -> dict[str, Any]:
    """Tabs component for read-only security data."""
    return {
        "id": "security-read-tabs",
        "type": "tabs",
        "props": {
            "tabs": [
                {"id": "findings", "label": "Findings",
                 "lazy_tool":
                     "security_security.list_persisted_findings"},
                {"id": "rules", "label": "Rules",
                 "lazy_tool":
                     "security_security.authoring.list_rules"},
                {"id": "health", "label": "Health & Config",
                 "lazy_tool":
                     "security_security.health_check"},
            ],
        },
    }


# ── Write-operation actions for the action_pane ────────────────────


def security_actions() -> list[dict[str, Any]]:
    """Return action definitions for the security action pane."""
    return [
        _analyze(),
        _threat_model(),
        _code_review(),
        _recon(),
        _get_analysis(),
    ]


def _analyze() -> dict[str, Any]:
    return {
        "id": "run-analysis", "label": "Run Analysis", "icon": "🔍",
        "tool": "security_security.analyze",
        "submit_label": "Run Analysis",
        "fields": [
            {"name": "target", "label": "Target", "type": "text",
             "placeholder": "https://example.com or /path/to/code",
             "tooltip": "URL, file path, or system description"},
            {"name": "analysis_type", "label": "Analysis Type",
             "type": "select",
             "options": [
                 {"value": "code_analysis", "label": "🔬 Code Analysis"},
                 {"value": "threat_model", "label": "🎯 Threat Model"},
                 {"value": "recon", "label": "🌐 Reconnaissance"},
                 {"value": "dependency_audit",
                  "label": "📦 Dependency Audit"},
             ],
             "tooltip": "Type of security analysis to perform"},
            {"name": "max_findings", "label": "Max Findings",
             "type": "range", "min": 1, "max": 100, "value": 50,
             "tooltip": "Cap the number of reported findings"},
        ],
    }


def _threat_model() -> dict[str, Any]:
    return {
        "id": "threat-model", "label": "Threat Model", "icon": "🎯",
        "tool": "security_security.threat_model",
        "submit_label": "Generate Model",
        "fields": [
            {"name": "target", "label": "Target", "type": "text",
             "placeholder": "Payment processing service",
             "tooltip": "System or component to threat-model"},
            {"name": "context", "label": "Context", "type": "textarea",
             "placeholder": "Handles PCI data, uses REST APIs...",
             "tooltip": "Additional context for the LLM analysis"},
        ],
    }


def _code_review() -> dict[str, Any]:
    return {
        "id": "code-review", "label": "Code Review", "icon": "📝",
        "tool": "security_security.code_review",
        "submit_label": "Review Code",
        "fields": [
            {"name": "code", "label": "Code", "type": "textarea",
             "placeholder": "def handle_request(data):\n    ...",
             "tooltip": "Paste code to review for security issues"},
            {"name": "language", "label": "Language", "type": "select",
             "options": [
                 {"value": "python", "label": "🐍 Python"},
                 {"value": "javascript", "label": "📜 JavaScript"},
                 {"value": "typescript", "label": "📘 TypeScript"},
                 {"value": "java", "label": "☕ Java"},
                 {"value": "go", "label": "🐹 Go"},
             ],
             "tooltip": "Programming language of the code snippet"},
            {"name": "focus", "label": "Focus Area", "type": "text",
             "placeholder": "injection, auth, crypto",
             "tooltip": "Narrow the review to specific concern areas"},
        ],
    }


def _recon() -> dict[str, Any]:
    return {
        "id": "recon", "label": "Reconnaissance", "icon": "🌐",
        "tool": "security_security.recon",
        "submit_label": "Run Recon",
        "fields": [
            {"name": "target", "label": "Target", "type": "text",
             "placeholder": "https://example.com",
             "tooltip": "URL or domain to perform recon against"},
            {"name": "depth", "label": "Depth", "type": "select",
             "options": [
                 {"value": "shallow", "label": "Shallow"},
                 {"value": "deep", "label": "Deep"},
             ],
             "tooltip": "Shallow is faster; deep is more thorough"},
        ],
    }


def _get_analysis() -> dict[str, Any]:
    return {
        "id": "get-analysis", "label": "Lookup Analysis", "icon": "📋",
        "tool": "security_security.get_analysis",
        "submit_label": "Lookup",
        "fields": [
            {"name": "analysis_id", "label": "Analysis ID",
             "type": "text", "placeholder": "analysis-abc123",
             "tooltip": "ID of a previous analysis to retrieve"},
        ],
    }
