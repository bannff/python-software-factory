"""Live migration acceptance — proves the Lessons/Memory import works end to end
against the owner's real KiroCrew snapshot, through the real MCP surface on the
isolated smoke instance (never the owner's live 3000/8000 stack).

Usage::

    uv run python projects/companion_x/scripts/migration_lessons_acceptance.py

Talks to the Next.js dashboard's MCP proxy at ``--next-base`` (default the
smoke instance's 13000), same transport/headers pattern as
``m1_session_fixture.py`` and ``m2_5_devtools_acceptance.py``.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from urllib.parse import urlparse

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--next-base", default="http://127.0.0.1:13000")
    return parser.parse_args()


async def _call(session: ClientSession, brick: str, tool: str, arguments: dict) -> dict:
    envelope = await session.call_tool(
        "call_brick_tool",
        arguments={
            "brick_name": brick, "tool_name": tool,
            "arguments": json.dumps(arguments),
        },
    )
    if envelope.is_error:
        raise RuntimeError(f"{brick}.{tool} transport failure: {envelope.content}")
    for block in envelope.content:
        if getattr(block, "type", None) == "text":
            data = json.loads(block.text)
            break
    else:
        raise RuntimeError(f"{brick}.{tool} returned no text content")
    if not isinstance(data, dict) or data.get("ok") is not True:
        raise RuntimeError(f"{brick}.{tool} outer envelope failed: {data}")
    outer = data.get("data")
    if not isinstance(outer, dict) or outer.get("ok") is not True:
        raise RuntimeError(f"{brick}.{tool} transport failed: {outer}")
    native = outer.get("result", {})
    inner = native.get("structured_content") if isinstance(native, dict) else None
    if not isinstance(inner, dict) or inner.get("ok") is not True:
        raise RuntimeError(f"{brick}.{tool} failed: {inner}")
    return inner["data"]


async def _run(next_base: str) -> None:
    parsed = urlparse(next_base)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise SystemExit("--next-base must be loopback HTTP")

    headers = {"Origin": next_base, "x-companion-x-local": "1"}
    http = create_mcp_http_client(headers=headers)
    async with http:
        async with streamable_http_client(f"{next_base}/mcp", http_client=http) as streams:
            async with ClientSession(*streams[:2]) as session:
                await session.initialize()

                preview = await _call(session, "migration", "migration_preview", {
                    "source": "kirocrew-v1", "kinds": ["lessons", "memory"],
                })
                reports = {r["kind"]: r for r in preview["reports"]}
                print("PREVIEW:", json.dumps(reports, indent=2))
                lessons_found = reports.get("lessons", {}).get("found", 0)
                lessons_eligible = reports.get("lessons", {}).get("eligible", 0)
                if lessons_found < 40:
                    raise RuntimeError(
                        f"expected ~49 lesson rows in preview, found {lessons_found} "
                        "— KIROCREW_IMPORT_ROOT may not be picked up by this process"
                    )
                if lessons_eligible == 0:
                    raise RuntimeError("all lesson rows excluded — check diagnostics above")

                start = await _call(session, "migration", "migration_start", {
                    "plan_digest": preview["plan_digest"], "kinds": ["lessons", "memory"],
                })
                run_id = start["run_id"]
                print("STARTED run_id:", run_id, "status:", start["status"])

                progress = None
                for _ in range(30):
                    progress = await _call(session, "migration", "migration_get", {
                        "run_id": run_id,
                    })
                    if progress["status"] not in {"running", "pending"}:
                        break
                    await asyncio.sleep(1)
                print("FINAL PROGRESS:", json.dumps(progress, indent=2))

                lessons_list = await _call(session, "lessons", "lessons_list", {"limit": 100})
                lesson_count = len(lessons_list["lessons"])
                print(f"lessons_list now returns {lesson_count} lessons")
                if lesson_count < 40:
                    raise RuntimeError(
                        f"expected ~49 lessons to be visible after import, got {lesson_count}"
                    )

                stats = await _call(session, "memory", "memory_stats", {})
                print("MEMORY STATS:", json.dumps(stats, indent=2))

                print("MIGRATION-ACCEPTANCE: PASS")


def main() -> int:
    asyncio.run(_run(_arguments().next_base))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
