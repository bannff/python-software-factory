"""Thin CLI caller for Workflow-managed registered graphs."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(name)s %(message)s")
logger = logging.getLogger("graph-runner")


def _write(path: Path, status: str, **values: object) -> None:
    path.write_text(json.dumps({"status": status, **values}, default=str))


async def main(args: argparse.Namespace) -> None:
    """Initialize the gateway, freeze the graph, and enroll Workflow."""
    status_file = Path(args.status_file)
    context = json.loads(args.context) if args.context else {}
    if isinstance(context.get("vuln_class"), str):
        context["vuln_class"] = context["vuln_class"].lower()
    _write(status_file, "initializing", run_id=context.get("run_id", ""))
    try:
        os.environ.setdefault("EAGER_LOAD", "0")
        from factory.mcp_server.interface import get_server
        get_server()
        from factory.agent.registry.defaults import get_default_graphs
        from factory.agent.registry.launch_validator import (
            skills_roots, validate_launch_context,
        )
        from factory.agent.runtime.managed_launch import (
            launch_managed_graph, new_run_key,
        )

        config = next(
            (graph for graph in get_default_graphs() if graph.id == args.graph_id),
            None,
        )
        if config is None:
            raise ValueError(f"Graph '{args.graph_id}' not found")
        errors = validate_launch_context(
            config.model_dump(by_alias=True), context,
            skills_dirs=skills_roots(),
        )
        if errors:
            raise ValueError(f"Launch validation failed: {errors[0]}")
        result = await launch_managed_graph(
            config, args.task, context,
            run_key=new_run_key(args.graph_id, requested=context.get("run_id")),
            origin_kind="registered", invocation_state={"launcher": "run_graph"},
        )
        payload = result.model_dump(mode="json")
        _write(status_file, result.status, **payload)
        logger.info("Managed graph enrolled: %s (%s)", result.run_id, result.status)
    except Exception as exc:
        logger.exception("Managed graph enrollment failed")
        _write(status_file, "failed", error=f"{type(exc).__name__}: {exc}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph-id", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--context", default="{}")
    parser.add_argument("--status-file", required=True)
    asyncio.run(main(parser.parse_args()))
