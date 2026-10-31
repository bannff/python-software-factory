"""Pytest adapter for bounded argv subprocess execution."""
from __future__ import annotations

import fnmatch
import re
import time
from pathlib import Path

from ..ports import TestDiscoveryResult, TestResult, TestRunner
from .bounded_subprocess import run_bounded


class PytestAdapter:
    """Test runner implementation using pytest."""

    def __init__(self, root_dir: str = ".", timeout_seconds: int = 300) -> None:
        self.root_dir = Path(root_dir).resolve()
        self.timeout_seconds = timeout_seconds

    def run_tests(
        self,
        path: str,
        pattern: str = "test_*.py",
        verbose: bool = False,
    ) -> TestResult:
        """Run pytest with bounded combined output and process cleanup."""
        test_path = self.root_dir / path
        if not test_path.exists():
            return TestResult(
                errors=[f"Path not found: {path}"],
                output=f"Error: Path {path} does not exist",
            )

        selected = self._matching_files(test_path, pattern)
        if selected == []:
            return TestResult(output=f"No tests found matching pattern: {pattern}")
        command = ["pytest"]
        if selected is None:
            command.extend([str(test_path), "-o", f"python_files={pattern}"])
        else:
            command.extend(str(item) for item in selected)
        command.append("-q")
        if verbose:
            command.append("-v")
        start_time = time.time()
        capture = run_bounded(
            command, cwd=self.root_dir, timeout=self.timeout_seconds
        )
        duration = time.time() - start_time
        if capture.error:
            return TestResult(errors=[capture.error], duration=duration)
        if capture.timed_out:
            return TestResult(
                errors=[f"Test execution timed out after {self.timeout_seconds} seconds"],
                output=capture.output + ("\n[output truncated]" if capture.truncated else ""),
                duration=duration,
            )
        output = capture.output + ("\n[output truncated]" if capture.truncated else "")
        return self._parse_pytest_output(
            output, "", capture.returncode, duration
        )

    def discover_tests(
        self,
        path: str,
        pattern: str = "test_*.py",
    ) -> TestDiscoveryResult:
        """Discover tests with bounded collection output and cleanup."""
        test_path = self.root_dir / path
        if not test_path.exists():
            return TestDiscoveryResult(errors=[f"Path not found: {path}"])

        selected = self._matching_files(test_path, pattern)
        if selected == []:
            return TestDiscoveryResult()
        command = ["pytest"]
        if selected is None:
            command.extend([str(test_path), "-o", f"python_files={pattern}"])
        else:
            command.extend(str(item) for item in selected)
        command.extend(["--collect-only", "-q"])
        capture = run_bounded(
            command,
            cwd=self.root_dir,
            timeout=60,
        )
        if capture.error:
            return TestDiscoveryResult(errors=[capture.error])
        if capture.timed_out:
            return TestDiscoveryResult(errors=["Test discovery timed out after 60 seconds"])
        if capture.truncated:
            return TestDiscoveryResult(errors=["Test discovery output truncated"])
        return self._parse_collect_output(capture.output, "", capture.returncode)

    def health_check(self) -> dict:
        """Check if pytest is available with a tiny bounded probe."""
        capture = run_bounded(
            ["pytest", "--version"], cwd=self.root_dir, timeout=10, max_output=4096
        )
        if capture.error or capture.timed_out:
            return {"status": "unhealthy", "backend": "pytest", "error": capture.error or "timeout"}
        version_match = re.search(r"pytest (\d+\.\d+\.\d+)", capture.output)
        return {
            "status": "healthy" if capture.returncode == 0 else "unhealthy",
            "backend": "pytest",
            "version": version_match.group(1) if version_match else "unknown",
            "root_dir": str(self.root_dir),
        }

    def _parse_pytest_output(
        self, stdout: str, stderr: str, returncode: int, duration: float
    ) -> TestResult:
        """Parse pytest output to extract pass/fail counts."""
        output = stdout + stderr
        passed = failed = skipped = 0
        for match in re.finditer(r"(\d+) (passed|failed|skipped)", output):
            count, status = int(match.group(1)), match.group(2)
            if status == "passed":
                passed = count
            elif status == "failed":
                failed = count
            else:
                skipped = count
        errors = []
        if returncode != 0 and failed == 0:
            errors.append(f"pytest exited with code {returncode}")
        return TestResult(
            passed=passed, failed=failed, skipped=skipped, duration=duration,
            output=output, errors=errors,
        )

    def _parse_collect_output(
        self, stdout: str, stderr: str, returncode: int = 0
    ) -> TestDiscoveryResult:
        """Parse pytest collection nodes without treating node names as errors."""
        test_files: list[str] = []
        test_count = 0
        node_pattern = re.compile(r"^\s*(?P<file>\S+?\.py)(?:::.+)\s*$")
        collection_error = re.compile(
            r"^\s*(?:ERROR(?:\s+collecting\b|:)|INTERNALERROR\b|"
            r"ImportError while loading conftest\b|E\s+)",
            re.IGNORECASE,
        )
        for line in stdout.splitlines():
            match = node_pattern.match(line)
            if match is None:
                continue
            test_count += 1
            file_path = match.group("file")
            if file_path not in test_files:
                test_files.append(file_path)
        diagnostics = stdout + stderr
        error_lines = [line for line in diagnostics.splitlines() if collection_error.match(line)]
        errors = []
        if returncode != 0 or error_lines:
            errors.append(diagnostics.strip() or f"pytest exited with code {returncode}")
        return TestDiscoveryResult(
            test_files=test_files, test_count=test_count, errors=errors
        )

    def _matching_files(self, test_path: Path, pattern: str) -> list[Path] | None:
        """Select explicit files when pytest's basename filter is insufficient."""
        normalized = pattern.replace("\\", "/")
        if test_path.is_file():
            return [test_path] if self._matches_pattern(test_path, normalized) else []
        if "/" not in normalized:
            return None
        return sorted(
            candidate for candidate in test_path.rglob("*.py")
            if candidate.is_file() and self._matches_pattern(candidate, normalized)
        )

    def _matches_pattern(self, path: Path, pattern: str) -> bool:
        try:
            relative = path.resolve().relative_to(self.root_dir).as_posix()
        except ValueError:
            relative = path.as_posix()
        return fnmatch.fnmatchcase(path.name, pattern) or fnmatch.fnmatchcase(relative, pattern)


assert isinstance(PytestAdapter(), TestRunner)
