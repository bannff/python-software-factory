"""One-shot host entrypoint for sweeping exited Sandbox Docker containers.

Intended for a host scheduler, independent of the MCP server process. It
never reads container logs, secret mounts, or evidence files.
"""

from __future__ import annotations

import argparse

from .adapters.docker_adapter import _run
from .adapters.uds_mount import _RunFn, sweep_orphans


def run_once(run: _RunFn = _run, *, check_only: bool = False) -> int:
    """Return nonzero if Docker is unavailable; otherwise sweep once."""
    code, _, _ = run([
        "docker", "version", "--format", "{{.Server.Version}}",
    ], timeout=5)
    if code != 0:
        return 1
    if not check_only:
        sweep_orphans(run)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sweep exited or timed-out Sandbox containers")
    parser.add_argument(
        "--check", action="store_true",
        help="verify Docker access without changing containers or networks",
    )
    args = parser.parse_args(argv)
    return run_once(check_only=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
