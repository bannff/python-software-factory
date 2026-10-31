"""Enroll a model-overridden SAST graph as a Workflow-managed run."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import time
import uuid
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(name)s %(message)s")
logger = logging.getLogger("sast-runner")


def _scan_context(args: argparse.Namespace, requested_id: str) -> dict[str, str]:
    return {
        "vuln_class": args.vuln_class.lower(),
        "target_app": args.target,
        "run_id": requested_id,
        "target_packages": args.target,
        "sast_workspace": args.workspace,
    }


async def main(args: argparse.Namespace) -> None:
    """Freeze a dynamic SAST config, enroll it, and report the durable run."""
    requested_id = f"sast-{args.target}-{uuid.uuid4().hex[:6]}"
    context = _scan_context(args, requested_id)
    logger.info("Requested run key: %s", requested_id)
    from factory.mcp_server.interface import get_aggregator, get_server
    get_server()
    aggregator = get_aggregator()
    if aggregator is None:
        raise RuntimeError("Aggregator not available")

    from factory.agent.interface import (
        launch_managed_graph, materialize_workflow_config,
    )
    from factory.agent.registry.defaults_code_scan import SAST_SCAN_GRAPH

    model_override = args.model or os.environ.get("SAST_SCAN_MODEL")
    config = materialize_workflow_config(
        SAST_SCAN_GRAPH, context, model_override=model_override,
    )
    logger.info("Frozen dynamic graph: %s (%d nodes)", config.id, len(config.nodes))
    enrolled = await launch_managed_graph(
        config,
        f"Scan {args.target} source code for {args.vuln_class} "
        "vulnerabilities. Read files from the workspace.",
        context,
        run_key=requested_id,
        origin_kind="dynamic",
        invocation_state={"launcher": "run_sast_scan"},
    )
    managed_run_id = enrolled.run_id
    logger.info("Managed run: %s (%s)", managed_run_id, enrolled.status)

    findings = []
    try:
        response = aggregator.invoke_tool(
            "graph_graph_find_entities", entity_type="SuspectedVuln",
            properties={"run_id": managed_run_id}, limit=100,
        )
        findings = (
            [entity.properties for entity in response.data.entities]
            if response and response.ok and response.data is not None else []
        )
    except Exception as exc:
        logger.warning("Graph query failed: %s", exc)

    scoring = {}
    gt_path = Path(
        f"projects/companion_x/challenges/{args.target}/gt_entries.json"
    )
    if gt_path.exists():
        from factory.evals.runtime.gt_scorer import score
        scoring = score(findings, json.loads(gt_path.read_text()))
        logger.info(
            "P/R/F1: %.2f/%.2f/%.2f",
            scoring["precision"], scoring["recall"], scoring["f1"],
        )

    report = {
        "run_id": managed_run_id,
        "run_key": enrolled.run_key,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "workflow": {
            "type": "managed_strands_graph", "graph_id": config.id,
            "scan_type": "SAST", "model_override": model_override,
            "manifest_digest": enrolled.manifest_digest,
            "attempt_id": enrolled.attempt_id,
            "attempt_revision": enrolled.attempt_revision,
        },
        "target": {"app": args.target, "vuln_class": args.vuln_class},
        "findings": findings,
        "scoring": scoring,
        "graph_result": {
            "status": enrolled.status, "result": enrolled.result,
            "error": enrolled.error,
        },
    }
    output = Path(f"projects/companion_x/runs/{managed_run_id}.json")
    output.write_text(json.dumps(report, indent=2, default=str))
    logger.info("Report written: %s", output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run managed SAST scan graph")
    parser.add_argument("--target", default="idor_warehouse")
    parser.add_argument("--vuln-class", default="IDOR")
    parser.add_argument("--workspace", default="/tmp/factory-sast")
    parser.add_argument("--model", default=None, help="Override every SAST node model")
    asyncio.run(main(parser.parse_args()))
