"""Native dispatch must leave a secret-safe trace when a handler fails (issue #304)."""
import logging

from factory.mcp_utils.runtime.tool_failure import log_dispatch_failure


def test_import_error_logs_tool_type_and_message(caplog):
    with caplog.at_level(logging.ERROR):
        log_dispatch_failure("evals_run_experiment", ImportError("cannot import name 'get_capture'"))
    text = caplog.text
    assert "evals_run_experiment" in text
    assert "ImportError" in text
    assert "get_capture" in text


def test_arbitrary_exception_logs_type_only(caplog):
    with caplog.at_level(logging.ERROR):
        log_dispatch_failure("t", RuntimeError("token=sekret"))
    assert "RuntimeError" in caplog.text
    assert "sekret" not in caplog.text
