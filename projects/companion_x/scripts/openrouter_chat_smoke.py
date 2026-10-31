"""Live OpenRouter → Companion-X AG-UI typed-tool smoke.

Start Companion-X with ``COMPANION_X_CHAT_MODEL=openrouter/<vendor>/<model>``
and ``OPENROUTER_API_KEY`` exported, then run:

    uv run python projects/companion_x/scripts/openrouter_chat_smoke.py \
        --confirm-live-cost

The fixed prompt sends no project data. Output contains event types and tool names
only; response bodies and credentials are never printed.
"""

from __future__ import annotations

import argparse
import json
import os
from urllib.parse import urlparse
from uuid import uuid4

import httpx

_REQUIRED_ORDER = (
    "RUN_STARTED",
    "TOOL_CALL_START",
    "TOOL_CALL_ARGS",
    "TOOL_CALL_END",
    "TOOL_CALL_RESULT",
    "RUN_FINISHED",
)
_FIXED_PROMPT = (
    "Call the deterministic health_check tool exactly once. "
    "After the tool returns, reply with only: health check complete."
)


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api-base",
        default=os.getenv("OPENROUTER_SMOKE_API_BASE", "http://127.0.0.1:8000"),
    )
    parser.add_argument("--confirm-live-cost", action="store_true")
    return parser.parse_args()


def _validate(args: argparse.Namespace) -> None:
    if not args.confirm_live_cost:
        raise SystemExit("refusing live model call without --confirm-live-cost")
    if not os.getenv("OPENROUTER_API_KEY", "").strip():
        raise SystemExit("OPENROUTER_API_KEY is required")
    model_selector = os.getenv("COMPANION_X_CHAT_MODEL", "").strip()
    if model_selector == "openrouter":
        if not os.getenv("OPENROUTER_MODEL", "").strip():
            raise SystemExit("OPENROUTER_MODEL is required")
    elif not model_selector.startswith("openrouter/"):
        raise SystemExit("COMPANION_X_CHAT_MODEL must select OpenRouter")
    parsed = urlparse(args.api_base)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise SystemExit("--api-base must be a loopback HTTP URL")


def _events(response: httpx.Response) -> list[dict]:
    events: list[dict] = []
    for line in response.iter_lines():
        if not line.startswith("data: "):
            continue
        event = json.loads(line[6:])
        if isinstance(event, dict):
            events.append(event)
        if len(events) > 500:
            raise RuntimeError("AG-UI event limit exceeded")
    return events


def _assert_order(events: list[dict]) -> list[str]:
    types = [str(event.get("type") or "") for event in events]
    positions = [types.index(kind) for kind in _REQUIRED_ORDER]
    if positions != sorted(positions):
        raise AssertionError(f"invalid AG-UI order: {types}")
    starts = [event for event in events if event.get("type") == "TOOL_CALL_START"]
    names = [str(event.get("toolCallName") or "") for event in starts]
    accepted = {"health_check", "agent_health_check"}
    if len(names) != 1 or names[0] not in accepted:
        raise AssertionError(f"expected one typed health-check tool call, got {names}")
    return types


def main() -> int:
    args = _args()
    _validate(args)
    run_id = f"openrouter-smoke-{uuid4().hex[:12]}"
    with httpx.Client(timeout=120.0) as client:
        with client.stream(
            "POST",
            f"{args.api_base.rstrip('/')}/ag-ui/run",
            json={
                "threadId": run_id,
                "runId": run_id,
                "messages": [{"role": "user", "content": _FIXED_PROMPT}],
            },
        ) as response:
            response.raise_for_status()
            types = _assert_order(_events(response))
    print("openrouter-ag-ui-smoke: PASS")
    print("events: " + " → ".join(types))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
