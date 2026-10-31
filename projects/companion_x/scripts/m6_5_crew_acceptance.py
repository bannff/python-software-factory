"""Live M6.5 Crew model/project acceptance through authenticated MCP + AG-UI."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import httpx

_STATE = Path("/tmp/python-factory-evidence/m6.5-live-state.json")
_PROMPT = """Use Devtools exactly as follows:
1. Read app.py and use its SHA-256 to edit answer() so it returns 2.
2. Run: python -m pytest -q
3. Read the git diff for app.py.
4. Attempt to read ../outside.txt so confinement refusal is observed.
Do not stage, commit, or push. Finish only: CREW ACCEPTANCE COMPLETE.
"""
_REQUIRED = {
    "devtools_read_file", "devtools_edit_file",
    "devtools_run_command", "devtools_git_diff",
}


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("run", "verify"))
    parser.add_argument("--next-base", default="http://127.0.0.1:13000")
    parser.add_argument("--project", type=Path)
    parser.add_argument("--model")
    return parser.parse_args()


def _base(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise SystemExit("--next-base must be loopback HTTP")
    return value.rstrip("/")


def _sse_json(text: str) -> dict:
    values = [json.loads(line[6:]) for line in text.splitlines() if line.startswith("data: ")]
    if len(values) != 1:
        raise RuntimeError("unexpected MCP response")
    return values[0]


def _mcp(client: httpx.Client, base: str, brick: str, tool: str, args: dict) -> dict:
    response = client.post(
        f"{base}/mcp",
        headers={
            "Origin": base, "x-companion-x-local": "1",
            "Accept": "application/json, text/event-stream",
        },
        json={
            "jsonrpc": "2.0", "id": uuid4().hex, "method": "tools/call",
            "params": {"name": "call_brick_tool", "arguments": {
                "brick_name": brick, "tool_name": tool,
                "arguments": json.dumps(args, separators=(",", ":")),
            }},
        },
    )
    response.raise_for_status()
    result = _sse_json(response.text)["result"]["structuredContent"]
    value = result.get("data", {}).get("result", {}).get("structured_content", {})
    if value.get("ok") is not True or not isinstance(value.get("data"), dict):
        raise RuntimeError(f"MCP {brick}.{tool} failed")
    return value["data"]


def _events(response: httpx.Response) -> list[dict]:
    events = []
    for line in response.iter_lines():
        if line.startswith("data: "):
            value = json.loads(line[6:])
            if isinstance(value, dict):
                events.append(value)
        if len(events) > 1200:
            raise RuntimeError("AG-UI event limit exceeded")
    return events


def _accept(events: list[dict], project: Path) -> list[str]:
    names = [str(event.get("toolCallName") or "") for event in events
             if event.get("type") == "TOOL_CALL_START"]
    missing = _REQUIRED - set(names)
    if missing or names.count("devtools_read_file") < 2:
        raise AssertionError(f"incomplete Devtools sequence: missing={sorted(missing)} got={names}")
    terminals = [event for event in events if event.get("activityType") == "terminal.command"]
    if not terminals or not any(event.get("replace") is True for event in terminals):
        raise AssertionError("Terminal activity did not reach a final snapshot")
    if "return 2" not in (project / "app.py").read_text():
        raise AssertionError("Crew did not edit the confined project")
    if not any(event.get("type") == "RUN_FINISHED" for event in events):
        raise AssertionError("AG-UI run did not finish")
    return names


def _run(client: httpx.Client, base: str, project: Path, model: str) -> None:
    project = project.resolve(strict=True)
    if not (project / "pyproject.toml").is_file() or not model.startswith("openrouter/"):
        raise SystemExit("run requires a marked project and explicit OpenRouter model")
    crew_id = f"m65-live-{uuid4().hex[:10]}"
    crew = _mcp(client, base, "agent", "create_crew", {
        "crew_id": crew_id, "name": "M6.5 live developer", "persona_id": "developer",
        "project": str(project), "workspace": "acceptance", "memory_scope": "m65-live",
        "model": model, "description": "Restart-safe Crew acceptance.",
        "triggers": ["implementation", "acceptance"],
    })["crew"]
    _mcp(client, base, "agent", "set_default_crew", {
        "crew_id": crew_id, "expected_revision": crew["revision"],
    })
    resolved = _mcp(client, base, "agent", "resolve_crew", {"crew_id": crew_id})
    session = _mcp(client, base, "session", "create", {
        "title": "M6.5 Crew acceptance", "agent_id": resolved["persona_id"],
        "model": resolved["model_id"], "project": resolved["project"],
        "workspace": resolved["workspace"], "crew_id": resolved["crew_id"],
        "memory_scope": resolved["memory_scope"], "origin": "m6.5-acceptance",
    })["session"]
    body = {
        "threadId": session["thread_id"], "runId": f"m65-{uuid4().hex[:12]}",
        "messages": [{"id": f"msg-{uuid4().hex}", "role": "user", "content": _PROMPT}],
        "state": {}, "tools": [], "context": [], "forwardedProps": {},
    }
    with client.stream(
        "POST", f"{base}/api/copilotkit/agent/companion_x/run",
        headers={"Origin": base, "x-companion-x-local": "1"}, json=body,
    ) as response:
        response.raise_for_status()
        names = _accept(_events(response), project)
    state = {
        "crew_id": crew_id, "session_id": session["session_id"],
        "thread_id": session["thread_id"], "project": str(project),
        "model": model, "memory_scope": "m65-live",
    }
    _STATE.parent.mkdir(parents=True, exist_ok=True)
    _STATE.write_text(json.dumps(state, indent=2) + "\n")
    print("m6.5-crew-live: PASS")
    print("tools: " + " -> ".join(names))


def _verify(client: httpx.Client, base: str) -> None:
    state = json.loads(_STATE.read_text())
    crew = _mcp(client, base, "agent", "get_crew", {"crew_id": state["crew_id"]})["crew"]
    roster = _mcp(client, base, "agent", "list_crews", {})
    resolved = _mcp(client, base, "agent", "resolve_crew", {"crew_id": state["crew_id"]})
    session = _mcp(client, base, "session", "get", {"session_id": state["session_id"]})["session"]
    expected = (state["crew_id"], state["model"], state["project"], state["memory_scope"])
    actual = (session["crew_id"], session["model"], session["project"], session["memory_scope"])
    if actual != expected or resolved["model_id"] != state["model"]:
        raise AssertionError("materialized Crew binding changed after restart")
    if crew["project"] != state["project"] or roster["default_id"] != state["crew_id"]:
        raise AssertionError("Crew/default did not survive restart")
    if "return 2" not in (Path(state["project"]) / "app.py").read_text():
        raise AssertionError("project edit did not survive restart")
    print("m6.5-crew-restart: PASS")


def main() -> int:
    args = _args()
    base = _base(args.next_base)
    with httpx.Client(timeout=240.0) as client:
        if args.phase == "run":
            if args.project is None or not args.model:
                raise SystemExit("run requires --project and --model")
            _run(client, base, args.project, args.model)
        else:
            _verify(client, base)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
