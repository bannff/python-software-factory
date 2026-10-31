"""Best-effort live working-directory probe for a PTY shell process."""
from __future__ import annotations

import os
import platform
import subprocess

_LSOF = ("/usr/sbin/lsof", "/usr/bin/lsof")


def process_cwd(pid: int, fallback: str) -> str:
    if platform.system() == "Linux":
        try:
            return os.readlink(f"/proc/{pid}/cwd")
        except OSError:
            return fallback
    if platform.system() == "Darwin":
        executable = next((path for path in _LSOF if os.path.isfile(path)), None)
        if executable:
            try:
                output = subprocess.run(
                    [executable, "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
                    capture_output=True, text=True, timeout=1.0, check=False,
                    env={"PATH": "/usr/bin:/bin:/usr/sbin"},
                ).stdout
                return next(
                    (line[1:] for line in output.splitlines()
                     if line.startswith("n") and len(line) > 1),
                    fallback,
                )
            except (OSError, subprocess.SubprocessError):
                pass
    return fallback


__all__ = ["process_cwd"]
