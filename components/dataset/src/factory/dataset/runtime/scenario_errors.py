"""Typed fail-closed ScenarioPack errors."""


class ScenarioPackError(ValueError):
    """Base error for invalid ScenarioPack operations."""


class ScenarioPackIntegrityError(ScenarioPackError):
    """Raised when an immutable reference or artifact fails verification."""


class ScenarioGenerationError(ScenarioPackError):
    """Raised when deterministic episode generation is incomplete or inconsistent."""
