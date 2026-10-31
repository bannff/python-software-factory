"""Capability errors for portable run-topology reads."""


class GraphTopologyUnsupportedError(RuntimeError):
    """The selected graph backend cannot execute bounded topology reads."""

    code = "unsupported_backend"

    def __init__(self, backend: str) -> None:
        self.backend = backend
        super().__init__(f"Graph run topology is unsupported for backend '{backend}'")


__all__ = ["GraphTopologyUnsupportedError"]
