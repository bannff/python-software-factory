"""Strict lifecycle identity carried by time-series training jobs."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TimeSeriesLifecycleIdentity(BaseModel):
    """Immutable exact framework and artifact identity for native lifecycles."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    backend: str = Field(strict=True, min_length=1)
    framework: str = Field(strict=True, min_length=1)
    framework_version: str = Field(strict=True, min_length=1)
    loader: str = Field(strict=True, min_length=1)
    artifact_format: str = Field(strict=True, min_length=1)
    verifier_identity: str = Field(strict=True, min_length=1)


class LifecycleIdentityView:
    """Read-only compatibility view over a job's frozen lifecycle identity."""

    lifecycle_identity: TimeSeriesLifecycleIdentity | None

    def __setattr__(self, name: str, value: object) -> None:
        if name == "lifecycle_identity":
            if name in self.__dict__:
                raise AttributeError("lifecycle_identity is frozen after job creation")
            if value is not None and not isinstance(value, TimeSeriesLifecycleIdentity):
                raise TypeError(
                    "lifecycle_identity must be a TimeSeriesLifecycleIdentity or None"
                )
        super().__setattr__(name, value)

    def _identity_value(self, name: str) -> str | None:
        identity = self.lifecycle_identity
        return getattr(identity, name) if identity is not None else None

    @property
    def backend(self) -> str | None:
        return self._identity_value("backend")

    @property
    def framework(self) -> str | None:
        return self._identity_value("framework")

    @property
    def framework_version(self) -> str | None:
        return self._identity_value("framework_version")

    @property
    def loader(self) -> str | None:
        return self._identity_value("loader")

    @property
    def artifact_format(self) -> str | None:
        return self._identity_value("artifact_format")

    @property
    def verifier_identity(self) -> str | None:
        return self._identity_value("verifier_identity")


__all__ = ["LifecycleIdentityView", "TimeSeriesLifecycleIdentity"]
