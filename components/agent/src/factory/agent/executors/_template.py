"""Single ``{{var}}`` template substitution helper.

Shared by executor modules to inject context variables into agent
system prompts. Mirrors the regex shape
of ``registry/launch_validator._resolve_template`` — the validator
uses the same pattern for templated skill refs and was deliberately
kept in sync (Wave 1 launch validator note).

Missing variables are left as-is; callers surface them via the
launch validator's ``Missing required context variable`` path.
"""
from __future__ import annotations

import re
from typing import Any


def inject_variables(template: str, context: dict[str, Any]) -> str:
    """Substitute ``{{var}}`` placeholders from ``context``."""
    result = template
    for key, value in context.items():
        result = re.sub(
            r"\{\{\s*" + re.escape(key) + r"\s*\}\}",
            str(value),
            result,
        )
    return result
