"""Immutable local manifest store for canonical failure patterns."""
from __future__ import annotations

from ..failure_pattern_builtins import builtin_failure_patterns
from ..failure_pattern_codec import pattern_ref, verify_failure_pattern
from ..failure_pattern_models import FailurePatternRef, FailurePatternSpec


class LocalFailurePatternStore:
    """Read-only store; built-ins are validated and indexed by immutable ref."""

    def __init__(self, patterns: tuple[FailurePatternSpec, ...] | None = None) -> None:
        values = patterns if patterns is not None else builtin_failure_patterns()
        self._patterns = {}
        for pattern in values:
            verify_failure_pattern(pattern)
            key = (pattern.pattern_id, pattern.version)
            if key in self._patterns:
                raise ValueError("duplicate immutable failure pattern identity/version")
            self._patterns[key] = pattern

    def list_refs(self) -> tuple[FailurePatternRef, ...]:
        return tuple(pattern_ref(self._patterns[key]) for key in sorted(self._patterns))

    def load(self, ref: FailurePatternRef) -> FailurePatternSpec:
        pattern = self._patterns.get((ref.pattern_id, ref.version))
        if pattern is None:
            raise ValueError("failure pattern is not approved")
        verify_failure_pattern(pattern)
        if pattern.digest != ref.digest:
            raise ValueError("failure pattern reference digest mismatch")
        return pattern

    def inspect(self, pattern_id: str, version: str = "") -> FailurePatternSpec:
        matches = [pattern for (identity, item_version), pattern in self._patterns.items()
                   if identity == pattern_id and (not version or version == item_version)]
        if len(matches) != 1:
            raise ValueError("failure pattern identity requires one approved version")
        verify_failure_pattern(matches[0])
        return matches[0]


__all__ = ["LocalFailurePatternStore"]
