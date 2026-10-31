"""C6 Canary — Record-type polymorphism in recipe executor."""

from __future__ import annotations

import pytest

from factory.dataset.runtime.contracts import DatasetRecipe
from factory.dataset.runtime.validation import (
    dispatch_validator,
    validate_can_frame_records,
    validate_generic_records,
)


class TestC6RecordPolymorphism:
    """Verify CAN frame records pass through the validator dispatch."""

    def test_can_record_passes_through_validator(self) -> None:
        """C6 core canary: CAN frame schema routes to correct validator."""
        recipe = DatasetRecipe(
            version="can-v1",
            stages=[{"name": "test"}],
            record_schema="can_frame",
        )
        records = [{"arbitration_id": "0x123", "data": "00FF"}]
        validated = list(dispatch_validator(records, record_schema="can_frame"))
        assert len(validated) == 1
        assert validated[0]["arbitration_id"] == "0x123"

    def test_recipe_has_record_schema_field(self) -> None:
        """DatasetRecipe must accept record_schema."""
        recipe = DatasetRecipe(
            version="v1",
            stages=[{"name": "s"}],
            record_schema="can_frame",
        )
        assert recipe.record_schema == "can_frame"

    def test_recipe_defaults_to_conversation(self) -> None:
        """record_schema defaults to conversation for backward compat."""
        recipe = DatasetRecipe(version="v1", stages=[{"name": "s"}])
        assert recipe.record_schema == "conversation"

    def test_generic_validator_passthrough(self) -> None:
        """Generic schema should pass records through unchanged."""
        records = [{"a": 1}, {"b": 2}]
        validated = list(validate_generic_records(records))
        assert validated == records

    def test_can_validator_rejects_non_dict(self) -> None:
        """CAN frame validator must reject non-dict records."""
        with pytest.raises(ValueError, match="must be a dict"):
            list(validate_can_frame_records(["not-a-dict"]))

    def test_dispatch_validator_unknown_schema(self) -> None:
        """Unknown schema should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown record_schema"):
            list(dispatch_validator([], record_schema="nope"))
