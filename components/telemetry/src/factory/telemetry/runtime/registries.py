from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from factory.telemetry.runtime.config import ExporterConfig, MetricDefinition


@dataclass
class MetricRegistry:
    definitions: dict[str, MetricDefinition]

    def as_list(self) -> list[dict[str, Any]]:
        return [d.model_dump() for d in self.definitions.values()]


@dataclass
class ExporterRegistry:
    exporters: dict[str, ExporterConfig]

    def as_list(self) -> list[dict[str, Any]]:
        return [e.model_dump() for e in self.exporters.values()]


@dataclass
class Registries:
    metrics: MetricRegistry
    exporters: ExporterRegistry


def load_metric_definitions(config_dir: Path) -> MetricRegistry:
    base = config_dir / "metrics"
    definitions: dict[str, MetricDefinition] = {}
    if not base.exists():
        return MetricRegistry(definitions={})

    for path in sorted(base.glob("*.yaml")):
        data = yaml.safe_load(path.read_text())
        if not data:
            continue
        if not isinstance(data, list):
            raise ValueError(f"metrics file must be a list: {path}")
        for item in data:
            d = MetricDefinition.model_validate(item)
            definitions[d.id] = d
    return MetricRegistry(definitions=definitions)


def load_exporters(config_dir: Path) -> ExporterRegistry:
    base = config_dir / "exporters"
    exporters: dict[str, ExporterConfig] = {}
    if not base.exists():
        return ExporterRegistry(exporters={})

    for path in sorted(base.glob("*.yaml")):
        data = yaml.safe_load(path.read_text())
        if not data:
            continue
        if not isinstance(data, dict):
            raise ValueError(f"exporter file must be a mapping: {path}")
        cfg = ExporterConfig.model_validate(data)
        exporters[cfg.id] = cfg

    return ExporterRegistry(exporters=exporters)
