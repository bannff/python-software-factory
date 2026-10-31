"""Tests for security core functionality."""

import pytest

from factory.security.core import COMPONENT_NAME, COMPONENT_VERSION, AnalysisType, Severity
from factory.security.runtime.adapters.mock import MockAnalyzerAdapter, MockLLMAdapter
from factory.security.runtime.models import SecurityConfig
from factory.security.runtime.runtime import SecurityRuntime


class TestSecurityCore:
    """Test core types and constants."""

    def test_component_metadata(self) -> None:
        """Test component metadata is defined."""
        assert COMPONENT_NAME == "security"
        assert COMPONENT_VERSION == "0.1.0"

    def test_analysis_types(self) -> None:
        """Test analysis type enum."""
        assert AnalysisType.THREAT_MODEL == "threat_model"
        assert AnalysisType.CODE_ANALYSIS == "code_analysis"
        assert AnalysisType.PEN_TEST == "pen_test"

    def test_severity_levels(self) -> None:
        """Test severity enum."""
        assert Severity.CRITICAL == "critical"
        assert Severity.HIGH == "high"
        assert Severity.LOW == "low"


class TestSecurityConfig:
    """Test security configuration model."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = SecurityConfig()
        assert config.max_findings == 100
        assert config.include_info is False
        assert config.timeout_seconds == 300

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = SecurityConfig(max_findings=50, include_info=True)
        assert config.max_findings == 50
        assert config.include_info is True


class TestMockAnalyzerAdapter:
    """Test mock analyzer adapter."""

    @pytest.fixture
    def adapter(self) -> MockAnalyzerAdapter:
        """Create mock adapter."""
        return MockAnalyzerAdapter()

    @pytest.mark.asyncio
    async def test_analyze(self, adapter: MockAnalyzerAdapter) -> None:
        """Test analysis."""
        result = await adapter.analyze("target", "code_analysis")
        assert "findings" in result
        assert len(result["findings"]) > 0
        assert result["findings"][0]["severity"] == "medium"

    def test_supported_types(self, adapter: MockAnalyzerAdapter) -> None:
        """Test supported types."""
        types = adapter.supported_types()
        assert "code_analysis" in types
        assert "threat_model" in types

    def test_health_check(self, adapter: MockAnalyzerAdapter) -> None:
        """Test health check."""
        health = adapter.health_check()
        assert health["healthy"] is True


class TestSecurityRuntime:
    """Test security runtime."""

    @pytest.fixture
    def runtime(self) -> SecurityRuntime:
        """Create runtime with mock adapters."""
        return SecurityRuntime(MockAnalyzerAdapter(), MockLLMAdapter())

    @pytest.mark.asyncio
    async def test_analyze(self, runtime: SecurityRuntime) -> None:
        """Test analysis."""
        result = await runtime.analyze("target", AnalysisType.CODE_ANALYSIS)
        assert result.analysis_id is not None
        assert result.status == "completed"
        assert len(result.findings) > 0

    @pytest.mark.asyncio
    async def test_threat_model(self, runtime: SecurityRuntime) -> None:
        """Test threat modeling."""
        result = await runtime.threat_model("web app", "e-commerce")
        assert "target" in result
        assert "analysis" in result

    @pytest.mark.asyncio
    async def test_list_analyses(self, runtime: SecurityRuntime) -> None:
        """Test listing analyses."""
        await runtime.analyze("target1", AnalysisType.CODE_ANALYSIS)
        await runtime.analyze("target2", AnalysisType.RECON)
        analyses = runtime.list_analyses()
        assert len(analyses) == 2

    def test_health_check(self, runtime: SecurityRuntime) -> None:
        """Test runtime health check."""
        health = runtime.health_check()
        assert health["healthy"] is True
        assert "analyzer" in health
        assert "llm" in health
