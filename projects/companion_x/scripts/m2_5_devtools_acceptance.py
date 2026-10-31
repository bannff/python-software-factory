"""Live M2.5 chat-only acceptance through Next BFF and CopilotKit AG-UI."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import httpx

_PROMPT = """Use the supplied Devtools exactly as follows:
1. Read app.py and use its SHA-256 to edit it so answer() returns 2.
2. Run: python -m pytest -q
3. Read the git diff for app.py.
4. Attempt to read ../outside.txt so the confinement refusal is observed.
Do not stage, commit, or push. Finish with only: DEVTOOLS ACCEPTANCE COMPLETE.
"""
_REQUIRED = {
    "devtools_read_file", "devtools_edit_file",
    "devtools_run_command", "devtools_git_diff",
}


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--next-base", default="http://127.0.0.1:13000")
    parser.add_argument("--project", required=True)
    parser.add_argument("--confirm-live-cost", action="store_true")
    return parser.parse_args()


def _validate(args: argparse.Namespace) -> Path:
    if not args.confirm_live_cost:
        raise SystemExit("refusing live model call without --confirm-live-cost")
    parsed = urlparse(args.next_base)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise SystemExit("--next-base must be loopback HTTP")
    project = Path(args.project).resolve(strict=True)
    if not (project / "pyproject.toml").is_file():
        raise SystemExit("fixture project marker is missing")
    return project


def _sse_json(text: str) -> dict:
    values = [json.loads(line[6:]) for line in text.splitlines() if line.startswith("data: ")]
    if len(values) != 1:
        raise RuntimeError("unexpected MCP response")
    return values[0]


def _mcp(client: httpx.Client, base: str, brick: str, tool: str, arguments: dict) -> dict:
    params = {
        "name": "call_brick_tool",
        "arguments": {
            "brick_name": brick, "tool_name": tool,
            "arguments": json.dumps(arguments, separators=(",", ":")),
        },
    }
    response = client.post(
        f"{base}/mcp",
        headers={
            "Origin": base, "x-companion-x-local": "1",
            "Accept": "application/json, text/event-stream",
        },
        json={"jsonrpc": "2.0", "id": uuid4().hex, "method": "tools/call", "params": params},
    )
    response.raise_for_status()
    result = _sse_json(response.text)["result"]
    outer = result["structuredContent"]
    transport = outer.get("data", {}).get("result", {}).get("structured_content", {})
    if transport.get("ok") is not True or not isinstance(transport.get("data"), dict):
        raise RuntimeError(f"MCP {brick}.{tool} failed")
    return transport["data"]


def _events(response: httpx.Response) -> list[dict]:
    events = []
    for line in response.iter_lines():
        if not line.startswith("data: "):
            continue
        value = json.loads(line[6:])
        if isinstance(value, dict):
            events.append(value)
        if len(events) > 1000:
            raise RuntimeError("AG-UI event limit exceeded")
    return events


def _accept(events: list[dict], project: Path) -> None:
    starts = [event for event in events if event.get("type") == "TOOL_CALL_START"]
    names = [str(event.get("toolCallName") or "") for event in starts]
    missing = _REQUIRED - set(names)
    if missing:
        raise AssertionError(f"missing Devtools calls: {sorted(missing)}; got {names}")
    if names.count("devtools_read_file") < 2:
        raise AssertionError("outside-root refusal was not attempted through chat")
    terminals = [event for event in events if event.get("activityType") == "terminal.command"]
    if not terminals or not any(event.get("replace") is True for event in terminals):
        raise AssertionError("Terminal activity did not open and close")
    if "return 2" not in (project / "app.py").read_text():
        raise AssertionError("developer edit did not land")
    if not any(event.get("type") == "RUN_FINISHED" for event in events):
        raise AssertionError("chat run did not finish")
    print("m2.5-devtools-chat: PASS")
    print("tools: " + " -> ".join(names))
    print(f"terminal_events: {len(terminals)}")


def main() -> int:
    args = _args()
    project = _validate(args)
    base = args.next_base.rstrip("/")
    run_id = f"m25-{uuid4().hex[:12]}"
    with httpx.Client(timeout=180.0) as client:
        session = _mcp(client, base, "session", "create", {
            "title": "M2.5 acceptance", "agent_id": "developer",
            "model": "openrouter", "origin": "m2.5-acceptance",
            "project": str(project),
        })["session"]
        body = {
            "threadId": session["thread_id"], "runId": run_id,
            "messages": [{"id": f"msg-{uuid4().hex}", "role": "user", "content": _PROMPT}],
            "state": {}, "tools": [], "context": [],
            "forwardedProps": {"companion_x_agent_id": "developer"},
        }
        with client.stream(
            "POST", f"{base}/api/copilotkit/agent/companion_x/run",
            headers={"Origin": base, "x-companion-x-local": "1"}, json=body,
        ) as response:
            response.raise_for_status()
            events = _events(response)
        _accept(events, project)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
