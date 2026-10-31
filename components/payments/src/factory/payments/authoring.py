import os
import yaml
from pathlib import Path
from typing import Dict, Any
from pydantic import BaseModel


class ProviderDefinition(BaseModel):
    id: str
    type: str  # stripe, mock, etc.
    enabled: bool = True
    config: Dict[str, Any]


class AuthoringManager:
    """
    Security-sensitive tools for managing provider configuration.
    Strictly scoped to config_dir.
    Disabled by default.
    """

    def __init__(self, config_dir: Path):
        self.config_dir = config_dir
        self.enabled = (
            os.environ.get("PAY_ENABLE_AUTHORING_TOOLS") == "1"
            or os.environ.get("PAYMENTS_ENABLE_AUTHORING_TOOLS") == "1"
        )

    def _check_enabled(self) -> None:
        if not self.enabled:
            raise PermissionError(
                "Authoring tools are disabled. Set PAY_ENABLE_AUTHORING_TOOLS=1 to enable."
            )

    def _resolve_path(self, filename: str) -> Path:
        """Prevent path traversal"""
        # Ensure we are only writing to config/providers/
        providers_dir = self.config_dir / "providers"
        target = (providers_dir / filename).resolve()
        try:
            target.relative_to(providers_dir)
        except ValueError:
            raise PermissionError(f"Path traversal attempt detected: {filename}")
        return target

    def get_status(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "config_dir": str(self.config_dir),
            "providers_dir": str(self.config_dir / "providers"),
        }

    def validate_provider_config(self, definition: Dict[str, Any], dry_run: bool = True) -> bool:
        self._check_enabled()
        # Validate against pydantic model
        try:
            ProviderDefinition(**definition)
        except Exception as e:
            raise ValueError(f"Invalid provider definition: {e}")
        return True

    def upsert_provider_definition(
        self, id: str, definition: Dict[str, Any], dry_run: bool = False
    ) -> str:
        self._check_enabled()
        self.validate_provider_config(definition, dry_run=True)

        if dry_run:
            return "Validation successful (dry_run)"

        filename = f"{id}.yaml"
        path = self._resolve_path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            yaml.dump(definition, f)

        return f"Provider definition saved to {path}"

    def delete_provider_definition(self, id: str) -> str:
        self._check_enabled()
        filename = f"{id}.yaml"
        path = self._resolve_path(filename)

        if path.exists():
            path.unlink()
            return f"Deleted {path}"
        else:
            return "File not found"


def is_authoring_enabled() -> bool:
    return (
        os.environ.get("PAY_ENABLE_AUTHORING_TOOLS") == "1"
        or os.environ.get("PAYMENTS_ENABLE_AUTHORING_TOOLS") == "1"
    )


def get_authoring_tools(config_dir: str | Path | None = None) -> AuthoringManager:
    if config_dir is None:
        config_dir = os.environ.get("PAYMENTS_CONFIG_DIR", "./config")
    return AuthoringManager(Path(config_dir))
