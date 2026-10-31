"""Docker CLI runner with secret environment filtering."""
from __future__ import annotations
import os
import subprocess
from factory.sandbox.runtime.adapters.secret_mounts import DITTO_LICENSE_ENV

def run(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """Run a subprocess synchronously, return (exit_code, stdout, stderr)."""
    import os
    import subprocess

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False,
            env={
                key: value for key, value in os.environ.items()
                if key != DITTO_LICENSE_ENV
            },
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "Command timed out"
    except FileNotFoundError:
        return 1, "", "docker CLI not found"
