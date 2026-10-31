"""Tests for BanditAnalyzerAdapter (bandit CLI wrapper).

Tests health_check with real bandit binary, mocks subprocess for
analyze() to avoid filesystem dependencies.
"""

from __future__ import annotations

import json

import pytest
from unittest.mock import patch, MagicMock

from factory.security.runtime.adapters.bandit_adapter import BanditAnalyzerAdapter


class TestBanditAnalyzerAdapter:
    """Tests for BanditAnalyzerAdapter."""

    def test_import(self) -> None:
        """Adapter is importable."""
        assert BanditAnalyzerAdapter is not None

    def test_instantiation(self) -> None:
        """Can create with default bandit command."""
        adapter = BanditAnalyzerAdapter()
        assert adapter is not None

    def test_supported_types(self) -> None:
        """Reports code_analysis as supported."""
        adapter = BanditAnalyzerAdapter()
        assert "code_analysis" in adapter.supported_types()

    def test_health_check_real(self) -> None:
        """health_check calls real bandit --version."""
        import shutil
        bandit_path = shutil.which("bandit")
        if bandit_path is None:
            pytest.skip("bandit not on PATH")
        adapter = BanditAnalyzerAdapter(bandit_cmd=bandit_path)
        health = adapter.health_check()
        assert health["adapter"] == "bandit"
        assert health["healthy"] is True
        assert "version" in health

    @pytest.mark.asyncio
    async def test_analyze_parses_json(self) -> None:
        """analyze() parses bandit JSON output into findings."""
        adapter = BanditAnalyzerAdapter()
        bandit_output = json.dumps({
            "results": [
                {
                    "test_id": "B101",
                    "test_name": "assert_used",
                    "issue_severity": "LOW",
                    "issue_text": "Use of assert detected.",
                    "filename": "test.py",
                    "line_number": 10,
                    "more_info": "https://bandit.readthedocs.io",
                },
            ],
            "metrics": {"_totals": {"loc": 50}},
        })

        mock_result = MagicMock()
        mock_result.stdout = bandit_output
        mock_result.returncode = 1  # bandit returns 1 when findings exist

        with patch("subprocess.run", return_value=mock_result):
            result = await adapter.analyze("target_dir", "code_analysis")

        assert len(result["findings"]) == 1
        finding = result["findings"][0]
        assert "B101" in finding["title"]
        assert finding["severity"] == "low"
        assert "test.py:10" in finding["location"]
        assert "50" in result["summary"]

    @pytest.mark.asyncio
    async def test_analyze_empty_output(self) -> None:
        """analyze() handles empty bandit output gracefully."""
        adapter = BanditAnalyzerAdapter()
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            result = await adapter.analyze("clean_dir", "code_analysis")

        assert result["findings"] == []

    @pytest.mark.asyncio
    async def test_analyze_timeout(self) -> None:
        """analyze() handles subprocess timeout."""
        import subprocess
        adapter = BanditAnalyzerAdapter()

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("bandit", 300)):
            result = await adapter.analyze("slow_dir", "code_analysis")

        assert result["findings"] == []
        assert "error" in result["summary"].lower()

    @pytest.mark.asyncio
    async def test_analyze_max_findings(self) -> None:
        """analyze() respects max_findings option."""
        adapter = BanditAnalyzerAdapter()
        many_results = [
            {"test_id": f"B{i}", "test_name": "test", "issue_severity": "LOW",
             "issue_text": "issue", "filename": "f.py", "line_number": i}
            for i in range(50)
        ]
        bandit_output = json.dumps({"results": many_results, "metrics": {"_totals": {"loc": 100}}})
        mock_result = MagicMock()
        mock_result.stdout = bandit_output

        with patch("subprocess.run", return_value=mock_result):
            result = await adapter.analyze("dir", "code_analysis", {"max_findings": 5})

        assert len(result["findings"]) == 5
