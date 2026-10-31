"""Fresh-process PTY child setup; never imported into the API event loop."""
from __future__ import annotations

import fcntl
import os
import sys
import termios


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(64)
    shell = sys.argv[1]
    fcntl.ioctl(0, termios.TIOCSCTTY, 0)
    os.environ["SHELL"] = shell
    os.environ.setdefault("TERM", "xterm-256color")
    os.execv(shell, [shell, "-l"])


if __name__ == "__main__":
    main()
