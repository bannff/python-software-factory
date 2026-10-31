"""Action form builder for Sandbox dashboard.

Exports:
- sandbox_action_form(): provision form + command/file action pane

Split from views.py to stay under 200 LOC per file.
"""

from __future__ import annotations

from typing import Any


def sandbox_action_form() -> dict[str, Any]:
    """Collapsible card with provision form and action pane."""
    return {
        "id": "sb-actions-card",
        "type": "card",
        "props": {
            "title": "Sandbox Actions",
            "icon": "⚡",
            "collapsible": True,
        },
        "children": [
            {
                "id": "sb-provision-form",
                "type": "form",
                "props": {
                    "tool": "sandbox_sandbox.provision",
                    "title": "Provision Sandbox",
                    "submit_label": "Provision",
                    "fields": [
                        {
                            "name": "instance_type",
                            "label": "Instance Type",
                            "type": "select",
                            "options": [
                                {"value": "t3.micro",
                                 "label": "t3.micro"},
                                {"value": "t3.small",
                                 "label": "t3.small"},
                                {"value": "t3.medium",
                                 "label": "t3.medium"},
                            ],
                            "tooltip": "EC2 instance size",
                        },
                        {
                            "name": "timeout_seconds",
                            "label": "Timeout (sec)",
                            "type": "number",
                            "min": 60, "max": 7200, "value": 3600,
                            "tooltip": "Auto-terminate after this duration",
                        },
                        {
                            "name": "auto_terminate",
                            "label": "Auto-Terminate",
                            "type": "select",
                            "options": [
                                {"value": "true", "label": "Yes"},
                                {"value": "false", "label": "No"},
                            ],
                            "tooltip": "Automatically terminate on timeout",
                        },
                    ],
                },
            },
            {
                "id": "sb-action-pane",
                "type": "action_pane",
                "props": {
                    "actions": _actions(),
                    "default_action": "execute-cmd",
                },
            },
        ],
    }


def _actions() -> list[dict[str, Any]]:
    """Write-operation actions for the sandbox action pane."""
    return [
        {
            "id": "execute-cmd", "label": "Execute Command",
            "icon": "⚡",
            "tool": "sandbox_sandbox.execute",
            "submit_label": "Run Command",
            "fields": [
                {"name": "env_id", "label": "Environment ID",
                 "type": "text", "placeholder": "env-abc123",
                 "tooltip": "Target sandbox environment"},
                {"name": "command", "label": "Command",
                 "type": "textarea",
                 "placeholder": "ls -la /workspace",
                 "tooltip": "Shell command to execute"},
                {"name": "timeout_seconds", "label": "Timeout (sec)",
                 "type": "number", "min": 1, "max": 3600,
                 "value": 300,
                 "tooltip": "Max execution time before kill"},
            ],
        },
        {
            "id": "get-status", "label": "Get Status", "icon": "📋",
            "tool": "sandbox_sandbox.get_status",
            "submit_label": "Check Status",
            "fields": [
                {"name": "env_id", "label": "Environment ID",
                 "type": "text", "placeholder": "env-abc123",
                 "tooltip": "Check current status of a sandbox"},
            ],
        },
        {
            "id": "upload-file", "label": "Upload File", "icon": "📤",
            "tool": "sandbox_sandbox.upload_file",
            "submit_label": "Upload",
            "fields": [
                {"name": "env_id", "label": "Environment ID",
                 "type": "text", "placeholder": "env-abc123",
                 "tooltip": "Target sandbox environment"},
                {"name": "local_path", "label": "Local Path",
                 "type": "text", "placeholder": "/tmp/script.py",
                 "tooltip": "Path to the local file"},
                {"name": "remote_path", "label": "Remote Path",
                 "type": "text",
                 "placeholder": "/workspace/script.py",
                 "tooltip": "Destination path inside sandbox"},
            ],
        },
        {
            "id": "terminate-env", "label": "⚠ Terminate",
            "icon": "🗑️",
            "tool": "sandbox_sandbox.terminate",
            "submit_label": "Terminate",
            "fields": [
                {"name": "env_id", "label": "Environment ID",
                 "type": "text", "placeholder": "env-abc123",
                 "tooltip": "Permanently terminate this sandbox"},
            ],
        },
    ]
