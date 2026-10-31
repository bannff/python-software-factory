from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

import pytest

from factory.devtools.runtime import command_runner
from factory.devtools.runtime.command_policy import CommandRefused, resolve_command
from factory.devtools.runtime.models import ProjectBinding
from factory.devtools.runtime.output_safety import OutputRefused
from factory.devtools.runtime.path_resolver import PathRefused


def _binding(tmp_path: Path) -> ProjectBinding:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='fixture'\nversion='0'\n")
    return ProjectBinding(
        tenant_id="tenant", owner_id="owner", session_id="session",
        root=str(tmp_path.resolve()),
    )


def _test_file(root: Path, body: str) -> None:
    (root / "test_sample.py").write_text(body)


def test_command_runs_in_pinned_project_with_minimal_env_and_events(
    tmp_path, monkeypatch,
) -> None:
    binding = _binding(tmp_path)
    _test_file(tmp_path, """import os

def test_env():
    assert os.getenv('AWS_PROFILE') is None
    assert os.getenv('OPENROUTER_API_KEY') is None
    print('\\x1b[31mSAFE\\x1b[0m\\x01')
""")
    events = []
    monkeypatch.setattr(command_runner.event_bus, "publish", events.append)
    result = command_runner.run_command(
        binding, ["python", "-m", "pytest", "-q", "-s"],
        correlation_id="chat-run",
    )
    assert result.exit_code == 0 and "SAFE" in result.stdout
    assert "\x1b" not in result.stdout and "\x01" not in result.stdout
    assert [item["event_type"] for item in events][0] == "devtools.command.started"
    assert [item["event_type"] for item in events][-1] == "devtools.command.finished"
    assert [item["payload"]["sequence"] for item in events] == list(range(1, len(events) + 1))
    assert "argument_digest" in events[0]["payload"] and "text" not in events[0]["payload"]

    assert all(item["correlation_id"] == "chat-run" for item in events)

@pytest.mark.parametrize("argv", [
    ["custom-tool", "--watch"], ["custom-tool", "--serve"],
    ["custom-tool", "/tmp/outside"], ["custom-tool", "../outside"],
    ["custom-tool", "https://example.test"], ["custom-tool", "--fix"],
])
def test_command_policy_allows_arbitrary_arguments(tmp_path, monkeypatch, argv) -> None:
    monkeypatch.setattr(
        "factory.devtools.runtime.command_policy.shutil.which",
        lambda name, path: sys.executable,
    )
    executable, resolved = resolve_command(tmp_path.resolve(), argv)
    assert Path(executable).resolve() == Path(sys.executable).resolve()
    assert resolved == tuple(argv)


def test_command_policy_refuses_only_unavailable_or_malformed_executable(
    tmp_path, monkeypatch,
) -> None:
    monkeypatch.setattr(
        "factory.devtools.runtime.command_policy.shutil.which",
        lambda name, path: None,
    )
    with pytest.raises(CommandRefused, match="unavailable"):
        resolve_command(tmp_path.resolve(), ["does-not-exist"])
    for argv in ([""], ["tool", "bad\x00argument"], []):
        with pytest.raises(CommandRefused):
            resolve_command(tmp_path.resolve(), list(argv))


def test_command_policy_allows_project_local_executable(tmp_path) -> None:
    executable = tmp_path / "project-tool"
    executable.write_text("#!/bin/sh\necho project-tool\n")
    executable.chmod(0o700)
    selected, argv = resolve_command(tmp_path.resolve(), [str(executable), "--custom"])
    assert Path(selected).resolve() == executable.resolve()
    assert argv == (str(executable), "--custom")


def test_output_cap_is_truthful(tmp_path) -> None:
    binding = _binding(tmp_path)
    _test_file(tmp_path, "def test_output():\n print('X' * 5000)\n")
    result = command_runner.run_command(
        binding, ["python", "-m", "pytest", "-q", "-s"], output_limit=1024,
    )
    assert result.exit_code == 0 and result.truncated is True
    assert len(result.stdout) == 1024


def test_credential_like_output_is_never_published(tmp_path, monkeypatch) -> None:
    binding = _binding(tmp_path)
    _test_file(tmp_path, "def test_output():\n print('api_key=abcdefghijklmnop')\n")
    events = []
    monkeypatch.setattr(command_runner.event_bus, "publish", events.append)
    with pytest.raises(OutputRefused):
        command_runner.run_command(
            binding, ["python", "-m", "pytest", "-q", "-s"],
        )
    rendered = repr(events)
    assert "abcdefghijklmnop" not in rendered
    assert events[-1]["payload"]["success"] is False


def test_timeout_kills_child_process_group(tmp_path, monkeypatch) -> None:
    binding = _binding(tmp_path)
    code = (
        "import subprocess,sys,time; "
        "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)']); "
        "open('child.pid','w').write(str(child.pid)); time.sleep(30)"
    )
    monkeypatch.setattr(
        command_runner, "resolve_command",
        lambda root, argv: (sys.executable, ("python", "-c", code)),
    )
    result = command_runner.run_command(
        binding, ["pytest", "-q"], timeout_seconds=1,
    )
    assert result.timed_out is True and result.cancelled is False
    pid_path = tmp_path / "child.pid"
    assert pid_path.exists(), "fixture must start the child before timeout"
    pid = int(pid_path.read_text())
    for _ in range(30):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.05)
    else:
        raise AssertionError("child process survived group timeout")


def test_cancel_event_terminates_command(tmp_path) -> None:
    binding = _binding(tmp_path)
    _test_file(tmp_path, "import time\ndef test_wait():\n time.sleep(30)\n")
    cancel = threading.Event()
    box = []
    thread = threading.Thread(target=lambda: box.append(command_runner.run_command(
        binding, ["python", "-m", "pytest", "-q"],
        timeout_seconds=30, cancel_event=cancel,
    )))
    thread.start()
    time.sleep(0.3)
    cancel.set()
    thread.join(timeout=3)
    assert not thread.is_alive()
    assert box[0].cancelled is True and box[0].timed_out is False


def test_command_cwd_symlink_escape_is_refused(tmp_path) -> None:
    binding = _binding(tmp_path)
    outside = tmp_path.parent / "outside-command"
    outside.mkdir(exist_ok=True)
    (tmp_path / "escape").symlink_to(outside, target_is_directory=True)
    with pytest.raises(PathRefused):
        command_runner.run_command(binding, ["pytest", "-q"], cwd="escape")
