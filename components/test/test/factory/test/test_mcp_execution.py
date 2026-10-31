"""Regression tests for typed MCP execution outcomes and bounded projection."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

from factory.test.interface import TestResult, TestRuntime
from factory.test.runtime.mcp_containment import McpTestRuntime


def _facade(tmp_path):
    (tmp_path / "target").mkdir()
    return McpTestRuntime(TestRuntime(root_dir=tmp_path, adapter_type="memory"))


def test_zero_failure_result_is_passed_but_adapter_error_is_not(tmp_path) -> None:
    facade = _facade(tmp_path)
    facade._runtime.run_tests = MagicMock(return_value=TestResult(passed=2))
    passed = facade.run_path("target", "test_*.py", False)
    assert passed["outcome"] == "passed"
    assert passed["success"] is True

    facade._runtime.run_tests = MagicMock(return_value=TestResult(errors=["adapter exploded at /secret/path"]))
    failed = facade.run_path("target", "test_*.py", False)
    assert failed["outcome"] == "error"
    assert failed["success"] is False
    assert failed["error"] == "adapter_error"
    assert "/secret/path" not in str(failed)


def test_timeout_and_missing_target_have_typed_outcomes(tmp_path) -> None:
    facade = _facade(tmp_path)
    facade._runtime.run_tests = MagicMock(return_value=TestResult(errors=["Test execution timed out after 3 seconds"]))
    timeout = facade.run_path("target", "test_*.py", False)
    assert timeout["outcome"] == "timeout"
    assert timeout["success"] is False
    assert timeout["errors"] == ["timeout"]

    facade._runtime.run_tests.reset_mock()
    missing = facade.run_path("missing", "test_*.py", False)
    assert missing["outcome"] == "missing_target"
    assert missing["error"] == "target_not_found"
    facade._runtime.run_tests.assert_not_called()


def test_output_redaction_and_truncation_are_explicit(tmp_path) -> None:
    facade = _facade(tmp_path)
    output = "password=secret-value " + ("x" * 2_500)
    files = [f"target/test_{index}.py" for index in range(101)]
    facade._runtime.run_tests = MagicMock(return_value=TestResult(output=output, test_files=files))
    result = facade.run_path("target", "test_*.py", False)
    assert len(result["output"]) == 2_000
    assert result["output_truncated"] is True
    assert "secret-value" not in result["output"]
    assert result["test_files_truncated"] is True
    assert len(result["test_files"]) == 100



def test_adversarial_credentials_urls_and_paths_are_redacted(tmp_path) -> None:
    facade = _facade(tmp_path)
    outside = tmp_path.parent / "outside-secret.py"
    payload = " ".join([
        "password=secret-password", "secret=secret-value", "token=token-value",
        "api_key=api-value", "client_secret=client-value", "private_key=private-value",
        "credential=credential-value", "AWS_SECRET_ACCESS_KEY=aws-secret",
        "AWS_ACCESS_KEY_ID=aws-id", "AWS_SESSION_TOKEN=aws-session",
        "DATABASE_URL=postgres://db-user:db-password@db.example",
        "DB_URL=mysql://db-user:db-password@db.example",
        "Authorization: Bearer bearer-value", "Authorization: Basic basic-value",
        "https://url-user:url-password@example.com", str(outside),
        "private_key=-----BEGIN PRIVATE KEY-----pem-secret-----END PRIVATE KEY-----",
        str(tmp_path / "inside.txt"), r"C:\Users\alice\outside.txt",
    ])
    facade._runtime.run_tests = MagicMock(return_value=TestResult(
        output=payload, test_files=[str(tmp_path / "inside.py"), str(outside), r"C:\Users\alice\x.py"]
    ))
    result = facade.run_path("target", "test_*.py", False)
    rendered = str(result)
    for secret in (
        "secret-password", "secret-value", "token-value", "api-value", "client-value",
        "private-value", "credential-value", "aws-secret", "aws-id", "aws-session",
        "db-password", "bearer-value", "basic-value", "url-password", "pem-secret",
    ):
        assert secret not in rendered
    assert "private_key=[redacted]" in result["output"]
    assert "private_key=[redacted]]" not in rendered
    assert str(outside) not in rendered
    assert str(tmp_path) not in rendered
    assert "C:\\Users\\alice" not in rendered
    assert "<test-root>" in result["output"] and "<path>" in result["output"]
    assert result["test_files"] == ["inside.py"]


def test_structured_credentials_authorization_and_single_segment_paths_are_redacted(tmp_path) -> None:
    facade = _facade(tmp_path)
    payload = " ".join([
        '{"password":"json-secret"}', '{"token": "json-token"}',
        '{"access_key": "access-secret"}',
        json.dumps({"password": 'escaped"secret'}),
        json.dumps(json.dumps({"token": "nested-secret"})),
        "Authorization=Bearer equals-token", '"Authorization": "Basic quoted-token"',
        "Authorization: Bearer bare-token", "/single-secret",
        r"\\server\share\secret.txt",
    ])
    facade._runtime.run_tests = MagicMock(return_value=TestResult(output=payload))
    result = facade.run_path("target", "test_*.py", False)
    rendered = str(result)
    for secret in (
        "json-secret", "json-token", "access-secret", "escaped\"secret", "nested-secret",
        "equals-token", "quoted-token", "bare-token", "single-secret", "secret.txt",
    ):
        assert secret not in rendered
    assert "<path>" in result["output"]


def test_projection_bounds_repeated_diagnostics(tmp_path) -> None:
    facade = _facade(tmp_path)
    facade._runtime.run_tests = MagicMock(return_value=TestResult(errors=["adapter exploded"] * 1_000))
    result = facade.run_path("target", "test_*.py", False)
    assert len(result["errors"]) <= 20
    assert result["diagnostics_truncated"] is True


def test_redaction_covers_prefixed_keys_uri_paths_and_traversal_identities(tmp_path) -> None:
    facade = _facade(tmp_path)
    payload = " ".join([
        "GITHUB_TOKEN=github-secret", "OPENAI_API_KEY=openai-secret",
        "DB_PASSWORD=db-secret", "FOO_PASSWORD=foo-secret", "X-API-Key: header-secret",
        "file:///tmp/outside dir/secret.py", "/tmp/outside dir/secret.py",
        r"C:relative\\secret.txt", r"\\server\share\secret file.txt",
    ])
    facade._runtime.run_tests = MagicMock(return_value=TestResult(output=payload))
    result = facade.run_path("target", "test_*.py", False)
    rendered = str(result)
    for secret in (
        "github-secret", "openai-secret", "db-secret", "foo-secret", "header-secret",
        "secret.py", "secret.txt",
    ):
        assert secret not in rendered
    assert "<path>" in result["output"]


def test_junit_projection_redacts_relative_traversal_identity(tmp_path) -> None:
    base = tmp_path / "base.xml"
    candidate = tmp_path / "candidate.xml"
    base.write_text("placeholder", encoding="utf-8")
    candidate.write_text("placeholder", encoding="utf-8")
    runtime = TestRuntime(root_dir=tmp_path, adapter_type="memory")
    runtime.compare_junit = MagicMock(return_value={
        "passed": False,
        "base": {"total": 1, "outcomes": {"failure": 1}},
        "candidate": {"total": 1, "outcomes": {"failure": 1}},
        "blocking": [{
            "identity": "../../secret.py::TestSecret::test_password",
            "phase": "call", "baseline_outcome": "failure",
            "candidate_outcome": "failure", "reason": "new_debt",
        }],
        "legacy": [], "resolved": [], "errors": [],
    })
    result = McpTestRuntime(runtime).compare_junit("base.xml", "candidate.xml")
    assert result["blocking"][0]["identity"].startswith("<external-path>::")
    assert "secret.py" not in str(result)
