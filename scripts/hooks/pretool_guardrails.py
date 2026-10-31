"""Prompt for confirmation on obviously destructive commands."""

from __future__ import annotations

import json
import sys


DESTRUCTIVE_PATTERNS = (
    "git reset --hard",
    "git checkout --",
    "git clean -fd",
    "git clean -xfd",
    "rm -rf /",
    "rm -rf ~",
    "rm -rf .",
    "sudo rm -rf",
)

BRANCH_PATTERNS = (
    "git checkout -b",
    "git switch -c",
)


def _load_event() -> object:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}


def _collect_strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        items: list[str] = []
        for key, item in value.items():
            items.append(str(key))
            items.extend(_collect_strings(item))
        return items
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            items.extend(_collect_strings(item))
        return items
    return []


def _emit(payload: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(payload))


def main() -> int:
    event = _load_event()
    haystack = "\n".join(_collect_strings(event)).lower()

    if any(pattern in haystack for pattern in DESTRUCTIVE_PATTERNS):
        _emit(
            {
                "systemMessage": "Potentially destructive command detected. Confirm intent and prefer a reversible alternative when possible.",
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "ask",
                    "permissionDecisionReason": "Potentially destructive command detected.",
                },
            }
        )
        return 0

    if any(pattern in haystack for pattern in BRANCH_PATTERNS):
        _emit(
            {
                "continue": True,
                "systemMessage": "Before creating a new branch, check whether an existing feat/fix/chore branch should be reused for this work.",
            }
        )
        return 0

    _emit({"continue": True})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())