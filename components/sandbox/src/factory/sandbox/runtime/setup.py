"""Post-provision setup command execution for sandbox profiles.

Kept separate from ``runtime.py`` so profile bootstrap logic (installing
tooling, etc.) stays SRP-clean and small. Best-effort by design: a failing
setup command is logged and summarized but never aborts provisioning — the
container is already up and remains usable.
"""
from __future__ import annotations

import time
from typing import Any

from .event_emitter import emit

_PER_COMMAND_TIMEOUT_SECONDS = 600
# Overall wall-clock budget for the whole setup sequence, so a hung/slow
# bootstrap can't block provision() for per_command * N in the worst case.
_TOTAL_BUDGET_SECONDS = 1200


async def run_setup_commands(
    adapter: Any, env_id: str, commands: list[str],
) -> list[dict[str, Any]]:
    """Run each profile setup command in order (best-effort).

    Returns a compact per-command summary (command truncated, exit_code,
    success, skipped) so the caller can surface a half-broken bootstrap.
    Secrets must never be passed here — commands are emitted (truncated) to
    the event log for observability.
    """
    results: list[dict[str, Any]] = []
    execute = getattr(adapter, "execute", None)
    if execute is None:
        return results

    started = time.monotonic()
    for command in commands:
        remaining = _TOTAL_BUDGET_SECONDS - (time.monotonic() - started)
        if remaining <= 0:
            results.append(
                {"command": command[:160], "exit_code": None,
                 "success": False, "skipped": "budget_exhausted"}
            )
            continue
        timeout = int(min(_PER_COMMAND_TIMEOUT_SECONDS, remaining))
        try:
            result = await execute(env_id, command, timeout)
            exit_code = (
                int(result.get("exit_code", 0)) if isinstance(result, dict) else 0
            )
        except Exception:  # noqa: BLE001 - best-effort bootstrap
            exit_code = 1
        summary = {
            "command": command[:160],
            "exit_code": exit_code,
            "success": exit_code == 0,
        }
        results.append(summary)
        emit(
            "sandbox.setup_command",
            {"env_id": env_id, "entity_id": f"sandbox-env-{env_id}", **summary},
        )
    return results
