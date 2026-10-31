from __future__ import annotations

import os
import re
import signal
import socket
import stat
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).parents[3]
SCRIPT = ROOT / "scripts" / "companion-x-ui.sh"
SHARED_TOKEN_FILE = ROOT / "projects" / "companion_x" / ".storage" / "local-mcp-token"
STALE_TOKEN = "stale-token-from-an-earlier-run-1234"
SENTINEL = "sentinel-that-must-survive-the-test"
TOKEN_SHAPE = re.compile(r"^[A-Za-z0-9._~-]{16,512}$")


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def test_launcher_refuses_an_already_owned_api_port() -> None:
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    port = listener.getsockname()[1]
    env = {**os.environ, "API_PORT": str(port), "NEXT_PORT": "39999"}
    try:
        result = subprocess.run(
            ["bash", str(SCRIPT)], cwd=ROOT, env=env,
            capture_output=True, text=True, timeout=15, check=False,
        )
    finally:
        listener.close()
    assert result.returncode != 0
    assert f"API port {port} is already in use" in result.stderr
    assert "Starting API" not in result.stdout


def test_launcher_refuses_a_fifo_at_the_token_path(tmp_path: Path) -> None:
    """A FIFO must not block the write: the open has to fail with ENXIO."""
    fifo = tmp_path / "local-mcp-token"
    os.mkfifo(fifo, 0o600)
    env = {
        **os.environ,
        "API_PORT": str(_free_port()),
        "NEXT_PORT": "39999",
        "MCP_LOCAL_TOKEN_FILE": str(fifo),
    }
    env.pop("MCP_LOCAL_AUTH_TOKEN", None)

    started = time.time()
    result = subprocess.run(
        ["bash", str(SCRIPT)], cwd=ROOT, env=env,
        capture_output=True, text=True, timeout=20, check=False,
    )
    assert time.time() - started < 15, "the launcher blocked on the FIFO"
    assert result.returncode != 0
    assert "could not persist the local MCP credential" in result.stderr
    assert stat.S_ISFIFO(os.stat(fifo).st_mode), "the FIFO was replaced"
    assert "Starting API" not in result.stdout


def test_launcher_rejects_a_relative_token_file_override() -> None:
    """A relative override would point the launcher and the dashboard at
    different files, so it is refused instead of resolved twice."""
    shared_before = SHARED_TOKEN_FILE.read_bytes() if SHARED_TOKEN_FILE.exists() else None
    env = {
        **os.environ,
        "API_PORT": str(_free_port()),
        "NEXT_PORT": "39999",
        "MCP_LOCAL_TOKEN_FILE": "relative/token/path",
    }
    env.pop("MCP_LOCAL_AUTH_TOKEN", None)

    result = subprocess.run(
        ["bash", str(SCRIPT)], cwd=ROOT, env=env,
        capture_output=True, text=True, timeout=20, check=False,
    )
    assert result.returncode != 0
    assert "MCP_LOCAL_TOKEN_FILE must be an absolute path" in result.stderr
    assert "relative/token/path" in result.stderr
    assert "Starting API" not in result.stdout
    shared_after = SHARED_TOKEN_FILE.read_bytes() if SHARED_TOKEN_FILE.exists() else None
    assert shared_after == shared_before, "the refused run still touched the shared token path"


def test_launcher_persists_the_local_mcp_credential(tmp_path: Path) -> None:
    """Behavioural cover for the credential write path.

    `uv`/`curl`/`npx` are stubbed so the launcher reaches the write path and
    then stays alive instead of booting the real API. `MCP_LOCAL_TOKEN_FILE`
    points into `tmp_path`, so the test never rewrites or deletes the
    repository's shared token file — a sentinel at that path proves it. The
    pre-existing `0644` file is the case `O_CREAT` alone would not fix: the
    mode must come from the opened descriptor, and the token must never reach
    stdout/stderr.
    """
    stubs = tmp_path / "bin"
    stubs.mkdir()
    env_dump = tmp_path / "api-env"
    (stubs / "uv").write_text(f'#!/usr/bin/env bash\nenv > "{env_dump}"\nsleep 60\n')
    (stubs / "curl").write_text("#!/usr/bin/env bash\nexit 22\n")
    (stubs / "npx").write_text("#!/usr/bin/env bash\nsleep 60\n")
    for name in ("uv", "curl", "npx"):
        (stubs / name).chmod(0o755)

    token_file = tmp_path / "local-mcp-token"
    token_file.write_text(STALE_TOKEN)
    os.chmod(token_file, 0o644)

    preexisting = SHARED_TOKEN_FILE.read_bytes() if SHARED_TOKEN_FILE.exists() else None
    if preexisting is None:
        SHARED_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        SHARED_TOKEN_FILE.write_text(SENTINEL)
        os.chmod(SHARED_TOKEN_FILE, 0o600)

    output = tmp_path / "launcher.log"
    env = {
        **os.environ,
        "PATH": f"{stubs}{os.pathsep}{os.environ['PATH']}",
        "API_PORT": str(_free_port()),
        "NEXT_PORT": "39999",
        "MCP_LOCAL_TOKEN_FILE": str(token_file),
    }
    env.pop("MCP_LOCAL_AUTH_TOKEN", None)

    token = ""
    try:
        with output.open("w") as sink:
            process = subprocess.Popen(
                ["bash", str(SCRIPT)], cwd=ROOT, env=env,
                stdout=sink, stderr=subprocess.STDOUT, start_new_session=True,
            )
            try:
                deadline = time.time() + 30
                while time.time() < deadline:
                    mode = stat.S_IMODE(token_file.stat().st_mode) if token_file.exists() else None
                    # The writer truncates before writing, so only a value that
                    # matches the token shape counts as "rewritten".
                    candidate = token_file.read_text().strip() if mode == 0o600 else ""
                    if candidate != STALE_TOKEN and TOKEN_SHAPE.match(candidate):
                        token = candidate
                        break
                    time.sleep(0.05)
                # Wait for the API child so its environment can be asserted too.
                while not env_dump.exists() and time.time() < deadline:
                    time.sleep(0.05)
            finally:
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                except ProcessLookupError:
                    pass
                process.wait(timeout=15)
    finally:
        shared_after = SHARED_TOKEN_FILE.read_bytes() if SHARED_TOKEN_FILE.exists() else None
        if preexisting is None and shared_after is not None:
            SHARED_TOKEN_FILE.unlink()

    assert shared_after == (SENTINEL.encode() if preexisting is None else preexisting), (
        "the launcher touched the shared token path instead of MCP_LOCAL_TOKEN_FILE"
    )
    captured = output.read_text()
    assert token, f"launcher did not rewrite the credential; log:\n{captured[:1200]}"
    assert TOKEN_SHAPE.match(token), "persisted value is not a local MCP token"
    assert env_dump.exists(), f"the API child never started; log:\n{captured[:1200]}"
    assert token not in captured, "the credential leaked into the launcher output"
    assert "(mode 0600)" in captured
    assert not token_file.exists(), "cleanup did not remove the launcher credential"

    api_env = env_dump.read_text()
    assert "NEXT_PUBLIC_MCP_LOCAL_AUTH_TOKEN" not in api_env
    assert f"MCP_LOCAL_AUTH_TOKEN={token}" in api_env
