"""MCP prompts for metrics module."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing import Any

from .templates import (
    get_define_metric_prompt,
    get_analyze_trend_prompt,
    get_configure_dashboard_prompt,
)

if TYPE_CHECKING:
    from ..runtime.runtime import MetricsRuntime


def register(mcp: Any, runtime: "MetricsRuntime") -> None:
    """Register MCP prompts for metrics."""

    @mcp.prompt()
    def define_metric(
        metric_id: str = "custom_metric",
        metric_type: str = "gauge",
        name: str = "Custom Metric",
    ) -> str:
        """Guide for defining a new metric.

        Args:
            metric_id: Unique metric identifier
            metric_type: Type (counter, gauge, histogram, composite)
            name: Human-readable metric name
        """
        return get_define_metric_prompt(metric_id, metric_type, name)

    @mcp.prompt()
    def analyze_trend(
        metric_id: str = "custom_metric",
        window: str = "7d",
        granularity: str = "1d",
    ) -> str:
        """Guide for analyzing metric trends.

        Args:
            metric_id: Metric to analyze
            window: Time window (e.g. 7d, 30d)
            granularity: Bucket size (e.g. 1h, 1d)
        """
        return get_analyze_trend_prompt(metric_id, window, granularity)

    @mcp.prompt()
    def configure_dashboard(focus: str = "portfolio") -> str:
        """Guide for setting up a metrics dashboard.

        Args:
            focus: Dashboard focus area (portfolio, risk, performance)
        """
        return get_configure_dashboard_prompt(focus)
