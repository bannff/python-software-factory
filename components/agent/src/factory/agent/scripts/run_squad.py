"""Squad container entrypoint — the self-boot 'mission runner' (#768 A).

Runs INSIDE a provisioned squad container: reads its mission, resolves the
SquadConfig, prepares the local toolbelt + (optional) phone-home client, runs
the embedded team, and writes a status file for the host/orchestrator.

Mission inputs (analog of scripts/run_graph.py):
  --squad-file PATH   a SquadConfig YAML (the event payload / mounted mission), OR
  --squad-id ID       resolve from a squads dir (--config-dir / SQUAD_CONFIG_DIR)
  --task / --task-file  the work to do
  --workspace DIR     the cloned target repo (default: /work)
  --status-file PATH  where to write terminal status JSON

Phone-home (optional, injected by the trusted host — never minted here):
  MCP_PROXY_SOCKET  mounted per-launch Unix socket (preferred; dialed, no TCP)
  MCP_PROXY_URL  MCP endpoint (nominal authority; over the socket when set)
  MCP_POLICY_ID  frozen launch policy id (`workload:<launch-id>`)
  SQUAD_ALLOW_SHELL=1 only after the host asserts container isolation
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)


class SquadRunStatus(BaseModel):
    """Typed terminal status the runner writes for the host/orchestrator."""

    model_config = ConfigDict(extra="forbid")

    status: str
    squad: str | None = None
    output: str | None = None
    error: str | None = None


def _write(status_file: Path, status: str, **fields: object) -> None:
    status_file.parent.mkdir(parents=True, exist_ok=True)
    status_file.write_text(SquadRunStatus(status=status, **fields).model_dump_json())


def _task(args: argparse.Namespace) -> str:
    if args.task_file:
        return Path(args.task_file).read_text()
    return args.task or ""


async def main(args: argparse.Namespace) -> None:
    from factory.agent.runtime.squad_runner import prepare_squad, run_squad

    status_file = Path(args.status_file)
    _write(status_file, "starting", squad=args.squad_id or args.squad_file)
    try:
        from factory.agent.runtime.squad_contracts import SquadConfig

        if args.squad_file:
            import yaml
            config = SquadConfig.model_validate(
                yaml.safe_load(Path(args.squad_file).read_text()) or {})
        else:
            config_dir = args.config_dir or os.environ.get("SQUAD_CONFIG_DIR", "")
            if not config_dir:
                raise ValueError("provide --squad-file or --squad-id + --config-dir")
            from factory.agent.registry.squads import SquadRegistry
            registry = SquadRegistry(Path(config_dir) / "squads")
            await registry.load()
            config = registry.get(args.squad_id)
            if config is None:
                raise ValueError(f"squad {args.squad_id!r} not found in {config_dir}")

        prepared = await prepare_squad(
            config, workspace=args.workspace,
            mcp_url=os.environ.get("MCP_PROXY_URL") or None,
            capability_policy_id=os.environ.get("MCP_POLICY_ID") or None,
            proxy_socket=os.environ.get("MCP_PROXY_SOCKET") or None,
            allow_shell=os.environ.get("SQUAD_ALLOW_SHELL") == "1",
        )
        _write(status_file, "running", squad=config.id)
        try:
            result = await run_squad(prepared, _task(args))
        finally:
            await prepared.aclose()
        _write(
            status_file, result.status, squad=config.id,
            output=(result.output or "")[:4000],
        )
        logger.info("squad %s finished: %s", config.id, result.status)
    except Exception as exc:  # noqa: BLE001 - terminal status for the orchestrator
        logger.exception("squad run failed")
        _write(status_file, "failed", error=f"{type(exc).__name__}: {exc}")
        raise


def _parse() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a squad inside its container.")
    parser.add_argument("--squad-file")
    parser.add_argument("--squad-id")
    parser.add_argument("--config-dir")
    parser.add_argument("--task", default="")
    parser.add_argument("--task-file")
    parser.add_argument("--workspace", default="/work")
    parser.add_argument("--status-file", default="/tmp/squad-status.json")
    return parser.parse_args()


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main(_parse()))
