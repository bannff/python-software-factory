"""Contract tests for the host-owned one-shot Docker sweep."""

from factory.sandbox.runtime import host_sweep


def test_one_shot_sweeps_after_docker_preflight() -> None:
    calls: list[list[str]] = []

    def fake_run(cmd, timeout=30):  # noqa: ANN001
        calls.append(cmd)
        if cmd[:3] == ["docker", "ps", "-a"]:
            return 0, "", ""
        return 0, "28.0.0", ""

    assert host_sweep.run_once(fake_run) == 0
    assert ["docker", "version", "--format", "{{.Server.Version}}"] in calls
    assert any(cmd[:3] == ["docker", "ps", "-a"] for cmd in calls)


def test_one_shot_fails_when_daemon_unavailable() -> None:
    calls: list[list[str]] = []

    def fake_run(cmd, timeout=30):  # noqa: ANN001
        calls.append(cmd)
        return 1, "", "Docker unavailable"

    assert host_sweep.run_once(fake_run) == 1
    assert len(calls) == 1


def test_check_only_never_sweeps() -> None:
    calls: list[list[str]] = []

    def fake_run(cmd, timeout=30):  # noqa: ANN001
        calls.append(cmd)
        return 0, "28.0.0", ""

    assert host_sweep.run_once(fake_run, check_only=True) == 0
    assert calls == [["docker", "version", "--format", "{{.Server.Version}}"]]
