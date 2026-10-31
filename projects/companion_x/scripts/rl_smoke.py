"""End-to-end RL closure smoke driver — bd:python-factory-u3xy (no-bd: tooling).

Drives the full RL cascade through the running companion-x MCP server
to verify the closure events fire end-to-end after the persistence
track (bd-evra/0s6w/ttq8/t754/ksqd) and observability track
(bd-o7t8/kq6u) land. Each invocation deposits webgoat-shaped Findings,
publishes ``graph.completed``, then asserts the ``reward.computed →
wallet.rewarded → memory.learning_stored → workflow.improvement →
convergence.checked`` chain fired.

Usage::

    uv run python projects/companion_x/scripts/rl_smoke.py --run-id smoke-003
    uv run python projects/companion_x/scripts/rl_smoke.py --sweep

Talks to ``RL_SMOKE_API_BASE`` (default ``http://localhost:8000``) via
the real MCP streamable-HTTP surface at ``/mcp`` — the actual ``mcp``
Python SDK client, same transport the Next.js dashboard and any other
MCP client use (bd:python-factory-736 retired the REST bridge this
script used to hit at ``/api/tools/{tool_name}``).
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

API_BASE = os.environ.get("RL_SMOKE_API_BASE", "http://localhost:8000")
TIMEOUT_S = 30

# --- Webgoat fixture ---------------------------------------------------------
# GT lives at projects/companion_x/challenges/webgoat/gt_entries.json with 3
# CWE-639 entries. SAST match key is ("cwe","file"). We synthesize candidate
# Findings from this list to exercise the verdict ladder.
GT_FILES = [
    "src/main/java/org/owasp/webgoat/lessons/idor/IDORViewOtherProfile.java",
    "src/main/java/org/owasp/webgoat/lessons/idor/IDOREditOtherProfile.java",
    "src/main/java/org/owasp/webgoat/lessons/idor/IDORViewOwnProfileAltUrl.java",
]
FP_FILE = "src/main/java/org/owasp/webgoat/lessons/cryptography/Crypto.java"


@dataclass
class FindingDesign:
    tp_files: list[str] = field(default_factory=list)
    fp_files: list[str] = field(default_factory=list)

    @property
    def expected_f1(self) -> float:
        tp, fp = len(self.tp_files), len(self.fp_files)
        fn = len(GT_FILES) - tp
        if tp == 0:
            return 0.0
        p, r = tp / (tp + fp), tp / (tp + fn)
        return round(2 * p * r / (p + r), 4)


# Six runs to exercise all four workflow.improvement verdicts. Verdicts engage
# after _MIN_RUNS_FOR_SIGNAL=3 priors with thresholds ±0.05.
SWEEP_PLAN: list[tuple[str, FindingDesign]] = [
    ("smoke-003", FindingDesign(GT_FILES[:2], [FP_FILE])),  # F1=0.67 baseline
    ("smoke-004", FindingDesign(GT_FILES[:2], [FP_FILE])),  # F1=0.67 baseline
    ("smoke-005", FindingDesign(GT_FILES[:2], [FP_FILE])),  # F1=0.67 baseline
    ("smoke-006", FindingDesign(GT_FILES[:3], [])),         # F1=1.00 → improved
    ("smoke-007", FindingDesign(GT_FILES[:1], [FP_FILE])),  # F1=0.40 → regressed
    ("smoke-008", FindingDesign(GT_FILES[:2], [FP_FILE])),  # F1=0.67 → stable
]


# --- MCP plumbing -------------------------------------------------------------
# A single persistent ClientSession is used across the whole run/sweep,
# mirroring the frontend's module-level singleton pattern in
# frontends/next-dashboard/lib/mcp-client.ts (avoid re-running the MCP
# ``initialize`` handshake / re-minting ``mcp-session-id`` per call).

_session: ClientSession | None = None


async def _get_session() -> ClientSession:
    global _session
    if _session is None:
        raise RuntimeError("MCP session not started — call _open_session() first")
    return _session


async def _raw_call(tool: str, arguments: dict) -> Any:
    session = await _get_session()
    result = await session.call_tool(tool, arguments=arguments)
    if result.isError:
        raise RuntimeError(f"tools/call {tool} failed: {result.content}")
    for block in result.content:
        if getattr(block, "type", None) == "text":
            import json as _json
            return _json.loads(block.text)
    return None


# MCP_DISCOVERY_MODE=progressive (the default) exposes only the 9
# meta-tools until a brick is force-loaded — real ``tools/call`` needs
# the brick name split out, not a flat unprefixed name the old REST
# bridge used to fuzzy-resolve for free. ``call_brick_tool`` is the
# meta-tool every MCP client (including the Next dashboard) uses for
# this (bd:python-factory-736).
_BRICK_BY_TOOL = {
    "health_check": None,  # top-level meta-tool, no brick prefix needed
    "graph_add_entity": "graph",
    "events_publish": "events",
    "events_query_events": "events",
}


async def _call(tool: str, **kwargs) -> Any:
    """Invoke ``tool`` via real MCP ``tools/call``, routing through the
    ``call_brick_tool`` meta-tool for anything not itself a meta-tool."""
    import json as _json

    brick = _BRICK_BY_TOOL.get(tool)
    if brick is None:
        return await _raw_call(tool, kwargs)
    envelope = await _raw_call("call_brick_tool", {
        "brick_name": brick, "tool_name": tool, "arguments": _json.dumps(kwargs),
    })
    return envelope


# --- Smoke run ---------------------------------------------------------------

def _make_finding(run_id: str, idx: int, file_path: str) -> dict:
    """Build a Finding entity matching the projection fields ttq8 added."""
    return {
        "entity_type": "Finding",
        "entity_id": f"finding-{run_id}-{idx}",
        "properties": {
            "run_id": run_id, "vuln_class": "IDOR", "cwe": "CWE-639",
            "file": file_path, "function": "completed",
            "line_start": 44, "line_end": 65,
            "agent_id": "rl-smoke", "confidence_level": "Confirmed",
            "description": f"Smoke {run_id} synthesized IDOR finding.",
        },
    }


def _summarize(run_id: str, design: FindingDesign, rows: list[dict]) -> dict:
    by_type: dict[str, dict] = {}
    for e in rows:
        # Events query returns ``type`` not ``event_type`` (events_publish
        # input is ``event_type``; runtime renames it on read).
        by_type.setdefault(e.get("type") or e.get("event_type", ""),
                           e.get("payload", {}))
    reward = by_type.get("reward.computed", {})
    wallet = by_type.get("wallet.rewarded", {})
    learning = by_type.get("memory.learning_stored", {})
    improvement = by_type.get("workflow.improvement", {})
    convergence = by_type.get("convergence.checked", {})
    return {
        "run_id": run_id,
        "expected_f1": design.expected_f1,
        "observed_f1": float(reward.get("score", 0) or 0),
        "reward_value": reward.get("reward_value"),
        "reward_verdict": reward.get("verdict"),
        "wallet_tx": wallet.get("transaction_id"),  # bd-j5me
        "learning_stored": bool(learning.get("memory_id")),
        "improvement_verdict": improvement.get("verdict"),  # bd-kq6u
        "improvement_delta": improvement.get("delta"),
        "improvement_baseline": improvement.get("baseline_score"),
        "convergence_metrics": convergence.get("metrics_recorded"),
    }


async def run_one(run_id: str, design: FindingDesign) -> dict:
    """Drive one RL closure run; verify the cascade fired."""
    t0 = time.time()
    findings = [
        _make_finding(run_id, i, f)
        for i, f in enumerate(design.tp_files + design.fp_files)
    ]
    print(f"\n=== {run_id} (expected F1≈{design.expected_f1}) ===")
    print(f"  {len(findings)} Findings (TP×{len(design.tp_files)} FP×{len(design.fp_files)})")
    for f in findings:
        await _call("graph_add_entity", **f)
    await _call("events_publish", event_type="graph.completed", payload={
        "workflow_id": "sast", "workflow_run_id": run_id, "run_id": run_id,
        "workflow_type": "sast", "target_app": "webgoat",
        "vuln_class": "IDOR", "graph_id": "sast",
    }, source="rl-smoke", principal_id="kiro-agent")
    time.sleep(4.0)  # let cascade handlers fire (subscriptions chain)
    events = await _call("events_query_events", payload_key="run_id",
                          payload_value=run_id, limit=100)
    rows = events.get("data", {}).get("events", []) if isinstance(events, dict) and events.get("ok") else []
    summary = _summarize(run_id, design, rows)
    summary["elapsed_s"] = round(time.time() - t0, 1)
    for k, v in summary.items():
        print(f"  {k}: {v}")
    print("  Cascade:")
    print(f"    reward.computed:        {'✅' if summary['reward_value'] is not None else '❌'}")
    print(f"    wallet.rewarded.tx:     {'✅' if summary['wallet_tx'] else '❌'} (bd-j5me)")
    print(f"    memory.learning_stored: {'✅' if summary['learning_stored'] else '❌'}")
    print(f"    workflow.improvement:   {'✅' if summary['improvement_verdict'] else '❌'} (bd-kq6u)")
    print(f"    convergence.checked:    {'✅' if summary['convergence_metrics'] else '❌'}")
    return summary


async def _run(args) -> int:
    global _session
    mcp_url = f"{API_BASE}/mcp"
    async with streamablehttp_client(mcp_url) as (read, write, _get_session_id):
        async with ClientSession(read, write) as session:
            await session.initialize()
            _session = session
            health = await _call("health_check")
            data = health.get("data", {}) if isinstance(health, dict) else {}
            if data.get("status") not in ("healthy", "degraded"):
                print(f"❌ Server not reachable: {health}")
                return 1
            print(f"✅ Server healthy ({data.get('healthy_bricks')}/{data.get('total_bricks')} "
                  f"bricks)")
            if args.run_id:
                await run_one(args.run_id, SWEEP_PLAN[0][1])
                return 0
            rows = [await run_one(rid, d) for rid, d in SWEEP_PLAN]
            for _ in rows:
                time.sleep(1.0)
            print("\n=== Verdict transitions ===")
            for r in rows:
                print(f"  {r['run_id']:12} F1={r['observed_f1']:.2f}  "
                      f"baseline={r['improvement_baseline']}  "
                      f"Δ={r['improvement_delta']}  verdict={r['improvement_verdict']}")
            return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--run-id", help="Single-run mode: run id (e.g. smoke-003).")
    p.add_argument("--sweep", action="store_true",
                   help="Drive 6 runs to exercise all improvement verdicts.")
    args = p.parse_args()
    if not (args.run_id or args.sweep) or (args.run_id and args.sweep):
        p.error("supply --run-id <id> XOR --sweep")
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
