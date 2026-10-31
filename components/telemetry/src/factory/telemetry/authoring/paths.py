"""Path management for telemetry authoring."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AuthoringPaths:
    """Paths for telemetry authoring operations."""
    
    root: Path

    @property
    def metrics_dir(self) -> Path:
        return self.root / "metrics"

    @property
    def exporters_dir(self) -> Path:
        return self.root / "exporters"

    @property
    def settings_file(self) -> Path:
        return self.root / "settings.yaml"
